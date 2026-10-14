import logging
import re
import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path, PurePath
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.datastructures import UploadFile

from api import db
from api.config import API_PUBLIC_URL, MAX_UPLOAD_BYTES, RETENTION_DAYS, STORAGE_DIR
from api.schemas import CreateJobRequest, CreateUploadRequest, DownloadLink, Job, TranscodeSettings, UploadTicket
from worker.Ffmpeg_script import InvalidInput, probeVideo, runFfmpeg
from worker.faster_whisper_script import run_faster_whisper

log = logging.getLogger(__name__)
router = APIRouter(tags=["jobs"])
Db = Annotated[sqlite3.Connection, Depends(db.get_db)]

# One job at a time so FFmpeg and Whisper don't compete for the CPU.
_executor = ThreadPoolExecutor(max_workers=1)

# Frontend setting keys -> FFmpeg values; only these can reach FFmpeg.
HEIGHTS = {"1080p": "1080", "720p": "720", "480p": "480"}
VIDEO_ENCODERS = {"h264": "libx264"}
AUDIO_ENCODERS = {"mp3": "libmp3lame"}
AUDIO_BITRATE = "128k"  # not a user option


def _job_from_row(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"], status=row["status"], file_name=row["file_name"],
        settings=TranscodeSettings.model_validate_json(row["settings"]), transcribe=bool(row["transcribe"]),
        created_at=row["created_at"], updated_at=row["updated_at"], expires_at=row["expires_at"],
        output_size_bytes=row["output_size_bytes"], has_transcript=row["transcript_key"] is not None,
        error=row["error"],
    )


def _job_row(conn: sqlite3.Connection, job_id: UUID | str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (str(job_id),)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found.")
    return row


def _finish(conn: sqlite3.Connection, job_id: str, status: str, error: str | None = None,
            output_key: str | None = None, transcript_key: str | None = None, size: int | None = None) -> None:
    with conn:
        conn.execute(
            """UPDATE jobs SET status = ?, error = ?, output_key = ?, transcript_key = ?,
                   output_size_bytes = ?, updated_at = ? WHERE id = ?""",
            (status, error, output_key, transcript_key, size, db.to_db(db.utcnow()), job_id),
        )


# Runs on the background thread. On AWS this is the EC2 worker's job, fed by SQS.
def process_job(job_id: str) -> None:
    conn = db.connect()
    try:
        row = _job_row(conn, job_id)
        with conn:
            conn.execute("UPDATE jobs SET status = 'processing', updated_at = ? WHERE id = ?",
                         (db.to_db(db.utcnow()), job_id))
        settings = TranscodeSettings.model_validate_json(row["settings"])
        src = STORAGE_DIR / row["input_key"]
        output_key = f"outputs/{job_id}/video_{settings.resolution}.mp4"
        out = STORAGE_DIR / output_key
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            has_audio = probeVideo(src)  # rejects anything that isn't a real MP4 video
            runFfmpeg(
                str(src), None, HEIGHTS[settings.resolution],
                None if settings.frame_rate == "original" else settings.frame_rate,
                VIDEO_ENCODERS[settings.video_codec], settings.encoding_speed, settings.quality,
                AUDIO_ENCODERS[settings.audio_codec], AUDIO_BITRATE, outputFile=out, brightness=settings.brightness,
            )
            transcript_key = None
            if row["transcribe"] and has_audio:
                # Transcribes our own output, not the raw upload; writes video_<res>_transcript.json beside it.
                if transcript_file := run_faster_whisper(str(out)):
                    transcript_key = Path(transcript_file).relative_to(STORAGE_DIR).as_posix()
            _finish(conn, job_id, "ready", output_key=output_key, transcript_key=transcript_key,
                    size=out.stat().st_size)
        except Exception as e:
            shutil.rmtree(out.parent, ignore_errors=True)  # don't keep partial outputs
            if isinstance(e, InvalidInput):
                _finish(conn, job_id, "failed", "This file couldn't be read as an MP4 video.")
            else:
                log.exception("job %s failed", job_id)
                _finish(conn, job_id, "failed", "Encoding failed. Try again later.")
    finally:
        conn.close()


# Step 1 of encoding: reserve an upload. On AWS this returns a presigned S3 POST instead.
@router.post("/uploads", status_code=201)
def create_upload(body: CreateUploadRequest, conn: Db) -> UploadTicket:
    if body.size_bytes > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Videos can be at most {MAX_UPLOAD_BYTES // 1024**2} MB.")
    upload_id = uuid4()
    key = f"uploads/{upload_id}.mp4"  # server-generated; the user's filename is display-only
    with conn:
        conn.execute("INSERT INTO uploads (id, file_name, key) VALUES (?, ?, ?)",
                     (str(upload_id), body.file_name, key))
    return UploadTicket(
        upload_id=upload_id, url=f"{API_PUBLIC_URL}/uploads/{upload_id}/file", fields={},
        max_size_bytes=MAX_UPLOAD_BYTES, expires_at=db.utcnow() + timedelta(minutes=15),
    )


# Step 2: the browser sends the file here (stand-in for uploading straight to S3).
@router.post("/uploads/{upload_id}/file", status_code=204)
async def receive_upload(upload_id: UUID, request: Request, conn: Db) -> None:
    # Reject oversized bodies before reading them (S3 enforces this with the POST policy).
    length = request.headers.get("content-length", "")
    if not length.isdigit() or int(length) > MAX_UPLOAD_BYTES + 64 * 1024:  # small allowance for form headers
        raise HTTPException(413, "This file is larger than the upload limit.")
    row = conn.execute("SELECT key FROM uploads WHERE id = ? AND received = 0", (str(upload_id),)).fetchone()
    if not row:
        raise HTTPException(404, "Upload not found or already received.")
    dest = STORAGE_DIR / row["key"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with request.form(max_files=1) as form:
        file = form.get("file")
        if not isinstance(file, UploadFile):
            raise HTTPException(400, "Missing file.")
        size = 0
        try:
            with dest.open("wb") as out:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:  # don't trust the declared size either
                        raise HTTPException(413, "This file is larger than the upload limit.")
                    out.write(chunk)
        except HTTPException:
            dest.unlink(missing_ok=True)
            raise
    with conn:
        conn.execute("UPDATE uploads SET received = 1 WHERE id = ?", (str(upload_id),))


# Step 3: record the job and start it in the background.
@router.post("/jobs", status_code=202)
def create_job(body: CreateJobRequest, conn: Db) -> Job:
    upload = conn.execute("SELECT * FROM uploads WHERE id = ?", (str(body.upload_id),)).fetchone()
    if not upload:
        raise HTTPException(404, "Upload not found.")
    if not upload["received"]:
        raise HTTPException(409, "The video hasn't finished uploading.")
    job_id, now = str(uuid4()), db.utcnow()
    try:
        with conn:
            conn.execute(
                """INSERT INTO jobs (id, upload_id, status, file_name, settings, transcribe, input_key,
                       created_at, updated_at, expires_at)
                   VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?)""",
                (job_id, upload["id"], upload["file_name"], body.settings.model_dump_json(by_alias=True),
                 body.transcribe, upload["key"], db.to_db(now), db.to_db(now),
                 db.to_db(now + timedelta(days=RETENTION_DAYS))),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "This upload already has a job.")
    _executor.submit(process_job, job_id)
    return _job_from_row(_job_row(conn, job_id))


@router.get("/jobs")
def list_jobs(conn: Db) -> list[Job]:
    return [_job_from_row(row) for row in conn.execute("SELECT * FROM jobs ORDER BY created_at DESC")]


# On AWS this returns a short-lived presigned S3 GET URL instead.
@router.get("/jobs/{job_id}/download")
def get_download_link(job_id: UUID, file: Literal["video", "transcript"]) -> DownloadLink:
    return DownloadLink(
        url=f"{API_PUBLIC_URL}/jobs/{job_id}/files/{file}",
        expires_at=db.utcnow() + timedelta(minutes=5),  # not enforced locally
    )


@router.get("/jobs/{job_id}/files/{file}")
def download_file(job_id: UUID, file: Literal["video", "transcript"], conn: Db) -> FileResponse:
    row = _job_row(conn, job_id)
    key = row["output_key"] if file == "video" else row["transcript_key"]
    if row["status"] != "ready" or not key:
        raise HTTPException(404, "File not available.")
    stem = re.sub(r"[^A-Za-z0-9._ -]", "_", PurePath(row["file_name"]).stem)[:100] or "video"  # safe filename
    resolution = TranscodeSettings.model_validate_json(row["settings"]).resolution
    filename = f"{stem}_{resolution}.mp4" if file == "video" else f"{stem}_transcript.json"
    return FileResponse(STORAGE_DIR / key, filename=filename, content_disposition_type="attachment")

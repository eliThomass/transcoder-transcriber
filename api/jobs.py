import logging
import re
import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path, PurePath
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from api import db, storage
from api.auth import CurrentUser
from api.config import MAX_UPLOAD_BYTES, RETENTION_DAYS
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

DownloadFile = Literal["video", "transcript", "srt"]


# Converts a jobs table row into the API's Job response.
def _job_from_row(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"], status=row["status"], file_name=row["file_name"],
        settings=TranscodeSettings.model_validate_json(row["settings"]), transcribe=bool(row["transcribe"]),
        created_at=row["created_at"], updated_at=row["updated_at"], expires_at=row["expires_at"],
        output_size_bytes=row["output_size_bytes"], has_transcript=row["transcript_key"] is not None,
        error=row["error"],
    )


# Any job by ID, for the background worker only. Routes use _user_job instead.
def _job_row(conn: sqlite3.Connection, job_id: UUID | str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (str(job_id),)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found.")
    return row


# A job owned by this user. Other users' jobs return 404, so their existence isn't revealed.
def _user_job(conn: sqlite3.Connection, job_id: UUID | str, user: sqlite3.Row) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM jobs WHERE id = ? AND user_id = ?", (str(job_id), user["id"])).fetchone()
    if not row:
        raise HTTPException(404, "Job not found.")
    return row


# Records a job's final status and output files.
def _finish(conn: sqlite3.Connection, job_id: str, status: str, error: str | None = None,
            output_key: str | None = None, transcript_key: str | None = None, size: int | None = None) -> None:
    with conn:
        conn.execute(
            """UPDATE jobs SET status = ?, error = ?, output_key = ?, transcript_key = ?,
                   output_size_bytes = ?, updated_at = ? WHERE id = ?""",
            (status, error, output_key, transcript_key, size, db.to_db(db.utcnow()), job_id),
        )


# Downloads the upload, encodes (and transcribes) it in a temp folder, then uploads the results to S3.
# Returns (output_key, transcript_key, output size). This is the part that moves to the EC2 worker.
def _encode(row: sqlite3.Row) -> tuple[str, str | None, int]:
    settings = TranscodeSettings.model_validate_json(row["settings"])
    prefix = f"outputs/{row['user_id']}/{row['id']}/"
    with tempfile.TemporaryDirectory() as tmp:  # deleted afterwards, even on failure
        src, out = Path(tmp) / "input.mp4", Path(tmp) / f"video_{settings.resolution}.mp4"
        storage.download(row["input_key"], src)
        has_audio = probeVideo(src)  # rejects anything that isn't a real MP4 video
        runFfmpeg(
            str(src), None, HEIGHTS[settings.resolution],
            None if settings.frame_rate == "original" else settings.frame_rate,
            VIDEO_ENCODERS[settings.video_codec], settings.encoding_speed, settings.quality,
            AUDIO_ENCODERS[settings.audio_codec], AUDIO_BITRATE, outputFile=out, brightness=settings.brightness,
        )
        output_key, transcript_key = prefix + out.name, None
        storage.upload(out, output_key, "video/mp4")
        if row["transcribe"] and has_audio:
            # Transcribes our own output, not the raw upload; writes video_<res>_transcript.json/.srt beside it.
            json_file, srt_file = run_faster_whisper(str(out))
            if json_file:
                transcript_key = prefix + Path(json_file).name
                storage.upload(json_file, transcript_key, "application/json")
                storage.upload(srt_file, _srt_key(transcript_key), "application/x-subrip")
        return output_key, transcript_key, out.stat().st_size


# The SRT is stored beside the JSON transcript, so only the JSON key goes in the DB.
def _srt_key(transcript_key: str) -> str:
    return PurePath(transcript_key).with_suffix(".srt").as_posix()


# Runs on the background thread: encodes a job and records the result. On AWS, SQS feeds this to EC2 workers.
def process_job(job_id: str) -> None:
    conn = db.connect()
    try:
        row = _job_row(conn, job_id)
        with conn:
            conn.execute("UPDATE jobs SET status = 'processing', updated_at = ? WHERE id = ?",
                         (db.to_db(db.utcnow()), job_id))
        try:
            output_key, transcript_key, size = _encode(row)
            _finish(conn, job_id, "ready", output_key=output_key, transcript_key=transcript_key, size=size)
        except InvalidInput:
            _finish(conn, job_id, "failed", "This file couldn't be read as an MP4 video.")
        except Exception:  # partial outputs in S3 expire with the outputs/ lifecycle rule
            log.exception("job %s failed", job_id)
            _finish(conn, job_id, "failed", "Encoding failed. Try again later.")
    finally:
        conn.close()


# Step 1 of encoding: reserve an upload and return a presigned S3 POST for it.
@router.post("/uploads", status_code=201)
def create_upload(body: CreateUploadRequest, conn: Db, user: CurrentUser) -> UploadTicket:
    if body.size_bytes > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Videos can be at most {MAX_UPLOAD_BYTES // 1024**2} MB.")
    upload_id = uuid4()
    key = f"uploads/{user['id']}/{upload_id}.mp4"  # server-generated; the user's filename is display-only
    with conn:
        conn.execute("INSERT INTO uploads (id, user_id, file_name, key) VALUES (?, ?, ?, ?)",
                     (str(upload_id), user["id"], body.file_name, key))
    form = storage.upload_form(key)  # step 2: the browser posts the file straight to S3
    return UploadTicket(
        upload_id=upload_id, url=form["url"], fields=form["fields"], max_size_bytes=MAX_UPLOAD_BYTES,
        expires_at=db.utcnow() + timedelta(seconds=storage.UPLOAD_URL_SECONDS),
    )


# Step 3: record the job and start it in the background.
@router.post("/jobs", status_code=202)
def create_job(body: CreateJobRequest, conn: Db, user: CurrentUser) -> Job:
    upload = conn.execute("SELECT * FROM uploads WHERE id = ? AND user_id = ?",
                          (str(body.upload_id), user["id"])).fetchone()
    if not upload:
        raise HTTPException(404, "Upload not found.")
    if not storage.exists(upload["key"]):
        raise HTTPException(409, "The video hasn't finished uploading.")
    job_id, now = str(uuid4()), db.utcnow()
    try:
        with conn:
            conn.execute(
                """INSERT INTO jobs (id, user_id, upload_id, status, file_name, settings, transcribe, input_key,
                       created_at, updated_at, expires_at)
                   VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?)""",
                (job_id, user["id"], upload["id"], upload["file_name"], body.settings.model_dump_json(by_alias=True),
                 body.transcribe, upload["key"], db.to_db(now), db.to_db(now),
                 db.to_db(now + timedelta(days=RETENTION_DAYS))),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "This upload already has a job.")
    _executor.submit(process_job, job_id)
    return _job_from_row(_job_row(conn, job_id))


# The user's own jobs, newest first.
@router.get("/jobs")
def list_jobs(conn: Db, user: CurrentUser) -> list[Job]:
    rows = conn.execute("SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC", (user["id"],))
    return [_job_from_row(row) for row in rows]


# A short-lived presigned S3 link to one of the user's output files.
@router.get("/jobs/{job_id}/download")
def get_download_link(job_id: UUID, file: DownloadFile, conn: Db, user: CurrentUser) -> DownloadLink:
    row = _user_job(conn, job_id, user)  # ownership check before signing anything
    key = row["output_key"] if file == "video" else row["transcript_key"]
    if key and file == "srt":
        key = _srt_key(key)
    expired = row["expires_at"] <= db.to_db(db.utcnow())  # lifecycle deletion can lag by a day
    # Also missing for jobs from before S3.
    if row["status"] != "ready" or not key or expired or not storage.exists(key):
        raise HTTPException(404, "File not available.")
    stem = re.sub(r"[^A-Za-z0-9._ -]", "_", PurePath(row["file_name"]).stem)[:100] or "video"  # safe filename
    resolution = TranscodeSettings.model_validate_json(row["settings"]).resolution
    filename = {"video": f"{stem}_{resolution}.mp4", "transcript": f"{stem}_transcript.json",
                "srt": f"{stem}_{resolution}.srt"}[file]
    return DownloadLink(
        url=storage.download_url(key, filename),
        expires_at=db.utcnow() + timedelta(seconds=storage.DOWNLOAD_URL_SECONDS),
    )

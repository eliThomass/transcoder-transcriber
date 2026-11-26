import logging
import re
import sqlite3
from datetime import timedelta
from pathlib import PurePath
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from api import db, queues, storage
from api.auth import CurrentUser
from api.config import MAX_UPLOAD_BYTES, RETENTION_DAYS
from api.schemas import (CreateJobRequest, CreateUploadRequest, DownloadLink, Job, TranscodeSettings, UploadTicket,
                         WorkerJobMessage)

log = logging.getLogger(__name__)
router = APIRouter(tags=["jobs"])
Db = Annotated[sqlite3.Connection, Depends(db.get_db)]

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


# A job owned by this user. Other users' jobs return 404, so their existence isn't revealed.
def _user_job(conn: sqlite3.Connection, job_id: UUID | str, user: sqlite3.Row) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM jobs WHERE id = ? AND user_id = ?", (str(job_id), user["id"])).fetchone()
    if not row:
        raise HTTPException(404, "Job not found.")
    return row


# The SRT is stored beside the JSON transcript, so only the JSON key goes in the DB.
def _srt_key(transcript_key: str) -> str:
    return PurePath(transcript_key).with_suffix(".srt").as_posix()


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


# Step 3: record the job and put it on the queue for the workers.
@router.post("/jobs", status_code=202)
def create_job(body: CreateJobRequest, conn: Db, user: CurrentUser) -> Job:
    upload = conn.execute("SELECT * FROM uploads WHERE id = ? AND user_id = ?",
                          (str(body.upload_id), user["id"])).fetchone()
    if not upload:
        raise HTTPException(404, "Upload not found.")
    if not storage.exists(upload["key"]):
        raise HTTPException(409, "The video hasn't finished uploading.")
    job_id, now = uuid4(), db.utcnow()
    try:
        with conn:
            conn.execute(
                """INSERT INTO jobs (id, user_id, upload_id, status, file_name, settings, transcribe, input_key,
                       created_at, updated_at, expires_at)
                   VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?)""",
                (str(job_id), user["id"], upload["id"], upload["file_name"], body.settings.model_dump_json(by_alias=True),
                 body.transcribe, upload["key"], db.to_db(now), db.to_db(now),
                 db.to_db(now + timedelta(days=RETENTION_DAYS))),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "This upload already has a job.")
    try:
        queues.send_job(WorkerJobMessage(
            job_id=job_id, user_id=user["id"], input_key=upload["key"],
            output_prefix=queues.output_prefix(user["id"], job_id),
            settings=body.settings, transcribe=body.transcribe, requested_at=now,
        ))
    except Exception:
        log.exception("couldn't enqueue job %s", job_id)
        with conn:
            conn.execute("DELETE FROM jobs WHERE id = ?", (str(job_id),))  # no ghost job the user can't retry
        raise HTTPException(503, "Couldn't start encoding. Try again later.")
    return _job_from_row(_user_job(conn, job_id, user))


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

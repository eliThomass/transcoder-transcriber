"""SQS for the API: sends jobs to the workers and applies what they report back on the results queue."""
import logging
import sqlite3
import threading
from uuid import UUID

import boto3
from pydantic import TypeAdapter, ValidationError

from api import db
from api.config import AWS_REGION, SQS_QUEUE_URL, SQS_RESULTS_URL
from api.schemas import WorkerJobMessage, WorkerJobStarted, WorkerReport

log = logging.getLogger(__name__)
_sqs = boto3.client("sqs", region_name=AWS_REGION)
_reports = TypeAdapter(WorkerReport)

# Worker error codes -> what the user sees. Internal detail stays in the worker's logs.
USER_ERRORS = {
    "invalid_input": "This file couldn't be read as an MP4 video.",
    "encode_failed": "Encoding failed. Try again later.",
}


# The only S3 folder a job's results may be in.
def output_prefix(user_id: str, job_id: UUID | str) -> str:
    return f"outputs/{user_id}/{job_id}/"


# Puts a job on the queue for the workers.
def send_job(message: WorkerJobMessage) -> None:
    _sqs.send_message(QueueUrl=SQS_QUEUE_URL, MessageBody=message.model_dump_json(by_alias=True))


# Applies one worker report. Jobs only move forward, so duplicate or out-of-order reports are harmless.
def apply_report(conn: sqlite3.Connection, report: WorkerReport) -> None:
    job_id, now = str(report.job_id), db.to_db(db.utcnow())
    if isinstance(report, WorkerJobStarted):
        with conn:
            conn.execute("UPDATE jobs SET status = 'processing', updated_at = ? WHERE id = ? AND status = 'queued'",
                         (now, job_id))
        return
    row = conn.execute("SELECT user_id FROM jobs WHERE id = ? AND status IN ('queued', 'processing')",
                       (job_id,)).fetchone()
    if not row:
        return  # unknown job, or already finished
    keys = [k for k in (report.output_key, report.transcript_key) if k]
    # Never let a report point a job at files outside its own folder (e.g. another user's).
    if report.status == "ready" and (not report.output_key or
                                     not all(k.startswith(output_prefix(row["user_id"], job_id)) for k in keys)):
        log.warning("job %s: rejected a result with unexpected keys %s", job_id, keys)
        report = report.model_copy(update={"status": "failed", "error": "encode_failed"})
    with conn:
        if report.status == "ready":
            conn.execute(
                """UPDATE jobs SET status = 'ready', output_key = ?, transcript_key = ?, output_size_bytes = ?,
                       error = NULL, updated_at = ? WHERE id = ?""",
                (report.output_key, report.transcript_key, report.output_size_bytes, now, job_id),
            )
        else:
            conn.execute("UPDATE jobs SET status = 'failed', error = ?, updated_at = ? WHERE id = ?",
                         (USER_ERRORS[report.error or "encode_failed"], now, job_id))


# Validates and applies one message, then deletes it. If applying fails, it stays on the queue for a retry.
def _handle(conn: sqlite3.Connection, message: dict) -> None:
    try:
        report = _reports.validate_json(message["Body"])
    except ValidationError:
        log.warning("dropped a malformed worker report")  # retrying won't fix it
    else:
        apply_report(conn, report)
    _sqs.delete_message(QueueUrl=SQS_RESULTS_URL, ReceiptHandle=message["ReceiptHandle"])


# Long-polls the results queue until `stop` is set. Runs on a background thread started with the API.
def consume_reports(stop: threading.Event) -> None:
    conn = db.connect()
    try:
        while not stop.is_set():
            try:
                response = _sqs.receive_message(QueueUrl=SQS_RESULTS_URL, MaxNumberOfMessages=10, WaitTimeSeconds=20)
                for message in response.get("Messages", []):
                    _handle(conn, message)
            except Exception:
                log.exception("results queue error; retrying in 5 s")
                stop.wait(5)
    finally:
        conn.close()

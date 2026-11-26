"""Job worker: long-polls the job queue, encodes (and transcribes) each video, uploads the results to S3 and reports back.

Run from the repo root with `uv run python -m worker.main`. Credentials come from the default boto3 chain:
your `aws login` profile locally, the instance role on EC2. It never touches the database.
"""
import logging
import os
import socket
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import boto3
from dotenv import load_dotenv
from pydantic import ValidationError

from api.schemas import WorkerJobMessage, WorkerJobResult, WorkerJobStarted
from worker.Ffmpeg_script import InvalidInput, probeVideo, runFfmpeg
from worker.faster_whisper_script import run_faster_whisper

load_dotenv(Path(__file__).resolve().parent.parent / ".env")  # local runs; on EC2 the container gets real env vars
BUCKET = os.environ["S3_BUCKET"]  # from the environment, never the message, so a forged job can't pick a bucket
JOBS_URL = os.environ["SQS_QUEUE_URL"]
RESULTS_URL = os.environ["SQS_RESULTS_URL"]
REGION = os.environ.get("AWS_REGION", "us-east-1")
WORKER_ID = socket.gethostname()
HEARTBEAT_SECONDS, VISIBILITY_SECONDS = 10 * 60, 30 * 60

# Setting keys -> FFmpeg values; only these can reach FFmpeg.
HEIGHTS = {"1080p": "1080", "720p": "720", "480p": "480"}
VIDEO_ENCODERS = {"h264": "libx264"}
AUDIO_ENCODERS = {"mp3": "libmp3lame"}
AUDIO_BITRATE = "128k"  # not a user option

log = logging.getLogger("worker")
_s3 = boto3.client("s3", region_name=REGION)
_sqs = boto3.client("sqs", region_name=REGION)


# Sends a started or result report to the API.
def _report(report: WorkerJobStarted | WorkerJobResult) -> None:
    _sqs.send_message(QueueUrl=RESULTS_URL, MessageBody=report.model_dump_json(by_alias=True))


# Uploads a local file to the bucket with its content type.
def _upload(path: Path | str, key: str, content_type: str) -> None:
    _s3.upload_file(str(path), BUCKET, key, ExtraArgs={"ContentType": content_type})


# Keeps the message hidden from other workers while a long job runs, past the queue's 1 h timeout.
@contextmanager
def _keep_hidden(receipt: str) -> Iterator[None]:
    stop = threading.Event()

    def heartbeat() -> None:
        while not stop.wait(HEARTBEAT_SECONDS):
            _sqs.change_message_visibility(QueueUrl=JOBS_URL, ReceiptHandle=receipt,
                                           VisibilityTimeout=VISIBILITY_SECONDS)

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()


# Encodes (and transcribes) one job in a temp folder, uploads the results, and returns (video key, transcript key, size).
# The keys are fixed per job, so running a redelivered job again just overwrites the same files.
def encode(job: WorkerJobMessage) -> tuple[str, str | None, int]:
    s = job.settings
    with tempfile.TemporaryDirectory() as tmp:  # deleted afterwards, even on failure
        src, out = Path(tmp) / "input.mp4", Path(tmp) / f"video_{s.resolution}.mp4"
        _s3.download_file(BUCKET, job.input_key, str(src))
        has_audio = probeVideo(src)  # rejects anything that isn't a real MP4 video
        runFfmpeg(
            str(src), None, HEIGHTS[s.resolution], None if s.frame_rate == "original" else s.frame_rate,
            VIDEO_ENCODERS[s.video_codec], s.encoding_speed, s.quality,
            AUDIO_ENCODERS[s.audio_codec], AUDIO_BITRATE, outputFile=out, brightness=s.brightness,
        )
        output_key, transcript_key = job.output_prefix + out.name, None
        _upload(out, output_key, "video/mp4")
        if job.transcribe and has_audio:
            # Transcribes our own output, not the raw upload; writes video_<res>_transcript.json/.srt beside it.
            json_file, srt_file = run_faster_whisper(str(out))
            if json_file:
                transcript_key = job.output_prefix + Path(json_file).name
                _upload(json_file, transcript_key, "application/json")
                _upload(srt_file, job.output_prefix + Path(srt_file).name, "application/x-subrip")
        return output_key, transcript_key, out.stat().st_size


# Runs one job and reports how it went. Errors become a "failed" report; only a crash leaves it for a retry.
def handle(job: WorkerJobMessage) -> None:
    log.info("job %s started", job.job_id)
    _report(WorkerJobStarted(job_id=job.job_id, worker_id=WORKER_ID))
    try:
        output_key, transcript_key, size = encode(job)
        result = WorkerJobResult(job_id=job.job_id, status="ready", output_key=output_key,
                                 transcript_key=transcript_key, output_size_bytes=size)
    except InvalidInput as e:
        log.warning("job %s: invalid input: %s", job.job_id, e)
        result = WorkerJobResult(job_id=job.job_id, status="failed", error="invalid_input")
    except Exception:
        log.exception("job %s failed", job.job_id)
        result = WorkerJobResult(job_id=job.job_id, status="failed", error="encode_failed")
    _report(result)
    log.info("job %s %s", job.job_id, result.status)


# Polls forever, one job at a time so FFmpeg and Whisper get the whole machine.
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log.info("worker %s polling %s", WORKER_ID, JOBS_URL)
    while True:
        response = _sqs.receive_message(QueueUrl=JOBS_URL, MaxNumberOfMessages=1, WaitTimeSeconds=20)
        for message in response.get("Messages", []):
            try:
                job = WorkerJobMessage.model_validate_json(message["Body"])
            except ValidationError:
                log.warning("left a malformed job message for the dead-letter queue")  # kept for inspection
                continue
            with _keep_hidden(message["ReceiptHandle"]):
                handle(job)
            # Deleted only after the results are uploaded and reported.
            _sqs.delete_message(QueueUrl=JOBS_URL, ReceiptHandle=message["ReceiptHandle"])


if __name__ == "__main__":
    main()

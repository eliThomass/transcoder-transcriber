# Pydantic mirror of frontend/src/api/types.ts. Keep the two in sync.
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


# camelCase JSON on the wire, snake_case in Python; unknown fields are rejected.
class Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


# Allowed values match frontend/src/config/transcodeOptions.ts, so nothing else can reach FFmpeg.
class TranscodeSettings(Model):
    resolution: Literal["1080p", "720p", "480p"]
    frame_rate: Literal["original", "24", "30", "60"]
    video_codec: Literal["h264"]
    encoding_speed: Literal[
        "ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"
    ]
    quality: Literal["18", "20", "23", "26", "28"]
    brightness: Literal["-0.2", "-0.1", "0", "0.1", "0.2"]
    audio_codec: Literal["mp3"]


class HealthResponse(Model):
    status: Literal["ok"] = "ok"


class CreateUploadRequest(Model):
    file_name: str = Field(min_length=1, max_length=255)
    content_type: Literal["video/mp4"]
    size_bytes: int = Field(gt=0)


class UploadTicket(Model):
    upload_id: UUID
    url: str
    fields: dict[str, str]
    max_size_bytes: int
    expires_at: datetime


class CreateJobRequest(Model):
    upload_id: UUID
    settings: TranscodeSettings
    transcribe: bool


class Job(Model):
    id: UUID
    status: Literal["queued", "processing", "ready", "failed"]
    file_name: str
    settings: TranscodeSettings
    transcribe: bool
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    output_size_bytes: int | None
    has_transcript: bool
    error: str | None


class DownloadLink(Model):
    url: str
    expires_at: datetime

"""S3 access for the API."""
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from api.config import AWS_REGION, MAX_UPLOAD_BYTES, S3_BUCKET

UPLOAD_URL_SECONDS = 10 * 60
DOWNLOAD_URL_SECONDS = 5 * 60

# One shared client (thread-safe); SigV4 is required for presigned URLs on new buckets.
_s3 = boto3.client("s3", region_name=AWS_REGION, config=Config(signature_version="s3v4"))


# A presigned POST that only accepts one MP4 of at most MAX_UPLOAD_BYTES at exactly this key.
def upload_form(key: str) -> dict:
    return _s3.generate_presigned_post(
        S3_BUCKET, key,
        Fields={"Content-Type": "video/mp4"},
        Conditions=[{"Content-Type": "video/mp4"}, ["content-length-range", 1, MAX_UPLOAD_BYTES]],
        ExpiresIn=UPLOAD_URL_SECONDS,
    )


# A short-lived GET link that downloads the object as `filename`.
def download_url(key: str, filename: str) -> str:
    return _s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key, "ResponseContentDisposition": f'attachment; filename="{filename}"'},
        ExpiresIn=DOWNLOAD_URL_SECONDS,
    )


# True if the object exists (HEAD returns a bare 404 when it doesn't).
def exists(key: str) -> bool:
    try:
        _s3.head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise


# Copies an object to a local file.
def download(key: str, path: Path) -> None:
    _s3.download_file(S3_BUCKET, key, str(path))


# Uploads a local file with its content type.
def upload(path: Path | str, key: str, content_type: str) -> None:
    _s3.upload_file(str(path), S3_BUCKET, key, ExtraArgs={"ContentType": content_type})

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")  # local secrets like the Cognito client secret; .env is gitignored

# The SQLite database lives under DATA_DIR (gitignored) until it moves to RDS.
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "local_data"))
DB_PATH = DATA_DIR / "app.sqlite3"

# Videos, outputs and transcripts live in S3 (see docs/aws-resources.md).
S3_BUCKET = os.environ.get("S3_BUCKET", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Jobs go to the EC2 workers on SQS_QUEUE_URL; they report back on SQS_RESULTS_URL.
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")
SQS_RESULTS_URL = os.environ.get("SQS_RESULTS_URL", "")

API_PUBLIC_URL = os.environ.get("API_PUBLIC_URL", "http://localhost:8000")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 500 * 1024 * 1024))
RETENTION_DAYS = 7  # matches the bucket's outputs/ lifecycle rule

# Login: Cognito managed login (see docs/aws-resources.md). The secret must only ever live on the API.
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
COGNITO_CLIENT_SECRET = os.environ.get("COGNITO_CLIENT_SECRET", "")
COGNITO_DOMAIN = os.environ.get("COGNITO_DOMAIN", "").rstrip("/")
COGNITO_REGION = COGNITO_USER_POOL_ID.split("_")[0]  # pool IDs look like us-east-1_abc123
COGNITO_ISSUER = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
SESSION_HOURS = 8
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true") != "false"  # browsers accept Secure cookies on localhost

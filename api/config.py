import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")  # local secrets like the Cognito client secret; .env is gitignored

# Everything is stored locally under DATA_DIR (gitignored) until S3 is wired up.
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "local_data"))
DB_PATH = DATA_DIR / "app.sqlite3"
STORAGE_DIR = DATA_DIR / "storage"  # stand-in for the S3 bucket; paths mirror S3 keys

API_PUBLIC_URL = os.environ.get("API_PUBLIC_URL", "http://localhost:8000")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 500 * 1024 * 1024))
RETENTION_DAYS = 7  # shown as "Expires in N days"; local files aren't auto-deleted yet

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

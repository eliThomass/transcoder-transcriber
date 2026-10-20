import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Everything is stored locally under DATA_DIR (gitignored) until S3 is wired up.
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "local_data"))
DB_PATH = DATA_DIR / "app.sqlite3"
STORAGE_DIR = DATA_DIR / "storage"  # stand-in for the S3 bucket; paths mirror S3 keys

API_PUBLIC_URL = os.environ.get("API_PUBLIC_URL", "http://localhost:8000")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 500 * 1024 * 1024))
RETENTION_DAYS = 7  # shown as "Expires in N days"; local files aren't auto-deleted yet

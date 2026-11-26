import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import auth, db, jobs, queues
from api.config import CORS_ORIGINS, S3_BUCKET, SQS_QUEUE_URL, SQS_RESULTS_URL
from api.schemas import HealthResponse


# On startup: check AWS settings, create the SQLite tables, and start reading worker reports.
@asynccontextmanager
async def lifespan(_: FastAPI):
    if not (S3_BUCKET and SQS_QUEUE_URL and SQS_RESULTS_URL):
        raise RuntimeError("Set S3_BUCKET, SQS_QUEUE_URL and SQS_RESULTS_URL in .env (see .env.example)")
    db.init_db()
    stop = threading.Event()
    threading.Thread(target=queues.consume_reports, args=(stop,), daemon=True).start()
    yield
    stop.set()


app = FastAPI(title="Transcoder API", lifespan=lifespan)

# The frontend runs on another port, so the browser needs CORS; list origins explicitly, never "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(auth.router)
app.include_router(jobs.router)


# Liveness check
@app.get("/health")
def health() -> HealthResponse:
    return HealthResponse()

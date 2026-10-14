from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import db, jobs
from api.config import CORS_ORIGINS
from api.schemas import HealthResponse


# Create the SQLite tables on startup.
@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Transcoder API", lifespan=lifespan)

# The frontend runs on another port, so the browser needs CORS; list origins explicitly, never "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(jobs.router)


@app.get("/health")
def health() -> HealthResponse:
    return HealthResponse()

# transcoder-transcriber
A cloud transcoder for videos that features transcribing capabilities. Built for CPSC 454 - Cloud Security at CSUF.

## What works now

Everything runs locally; AWS isn't wired up yet.

1. On the **Encode** tab, pick an MP4, choose settings, and optionally ask for a transcript.
2. The API saves the upload, encodes it with FFmpeg, and transcribes it with faster-whisper.
3. The **Library** tab lists your jobs (queued, processing, ready or failed) with buttons to download the encoded video and the transcript (JSON with the full text and timestamped segments).

Uploaded videos, encoded outputs and transcripts are saved in `local_data/storage/`, and job info is in `local_data/app.sqlite3` (both gitignored).

**No access control yet:** there are no accounts, so anyone who can reach the API can upload files and see or download every job. Only run it on your own machine (`fastapi dev` listens on `127.0.0.1` by default).

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/), Node.js, and FFmpeg on your PATH (`brew install ffmpeg` / `apt install ffmpeg`).

Terminal 1, from the project root (API at http://localhost:8000, docs at http://localhost:8000/docs):

```bash
uv sync
uv run fastapi dev api/main.py
```

Terminal 2:

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173
```

Then open http://localhost:5173, encode a video, and log in (any email and password; login is mocked for now) to see it in the Library. The Library doesn't refresh on its own, so reload it to see a job's status change.

The first transcript downloads the Whisper model. The default `medium.en` is about 1.5 GB and slow on a CPU; for quicker local runs start the API with `WHISPER_MODEL=base uv run fastapi dev api/main.py` (or `tiny`).

## Backend

```
api/
  main.py                  FastAPI app, CORS, /health
  jobs.py                  upload, job, list and download routes; runs jobs one at a time on a background thread
  db.py                    SQLite tables for uploads and jobs
  schemas.py               request/response models (mirror frontend/src/api/types.ts)
  config.py                settings, overridable with env vars
worker/
  Ffmpeg_script.py         runFfmpeg() encodes a video; probeVideo() checks an upload first
  faster_whisper_script.py run_faster_whisper() writes a JSON transcript
  converter.py             JSON -> SRT subtitles (in progress)
```

The API maps the frontend's setting keys (e.g. `'720p'`, `'h264'`) to FFmpeg values from its own whitelist, then calls the worker functions. Later, these functions move to EC2 workers fed by SQS, and `local_data/` is replaced by S3.

To test the FFmpeg script on its own, put a video in `videos_un/` and run `uv run python worker/Ffmpeg_script.py` (output goes to `videos_pro/`).

## Frontend (React + Vite)

Other scripts: `npm run build` (type-checks, then builds) and `npm run lint`.

### What's there

- **Encode tab:** pick an MP4 (click or drag it in), choose a Low, Medium, High or Custom preset, adjust individual settings, and optionally request a transcript.
- **Library tab:** your past jobs with their status, expiry date, and download buttons for the video and transcript. The expiry date is a label for now; local files aren't deleted automatically.
- **Log in / Sign up:** buttons in the top bar open a dialog. Accounts aren't built yet, so in `npm run dev` any email and password logs in with mock data.

Only MP4 input, H.264 video and MP3 audio are supported for now.

### Layout

```
frontend/src/
  api/types.ts       request/response types (the API contract)
  api/client.ts      fetch wrapper used by every API call
  auth/authApi.ts    sign up, log in, log out, current user
  jobs/jobsApi.ts    upload, create/list/delete jobs, download links
  config/            API routes and flags, encode options and presets, tabs
  pages/             Encode (UploadPage) and Library pages
  components/        top bar, login dialog, select field
  dev/               dev-only helpers (mock API, FFmpeg command preview)
  styles/global.css  colors, fonts and shared styles
```

### Connecting to the backend

All endpoint paths are in `src/config/api.ts`, and all request and response shapes are in `src/api/types.ts`. The FastAPI models use the same names and fields, in camelCase JSON.

Each feature has a flag in `API_CONNECTED`. `jobs` is `true` (Encode and Library use the real API). `auth` is `false`, so:

- `npm run dev` logs in with fake data from `src/dev/mockApi.ts`.
- A production build (`npm run build`) shows "Accounts aren't available yet", so the Library can't be reached there until auth is built.

The API address defaults to `http://localhost:8000`. To change it, copy `.env.example` to `.env.local` and set `VITE_API_BASE_URL`. Anything starting with `VITE_` ends up in the public JavaScript, so never put secrets there.

### Dev-only extras

In `npm run dev`, the Encode page shows the FFmpeg command your settings would produce, with a copy button. It and the mock API are left out of production builds.

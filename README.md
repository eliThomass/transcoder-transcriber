# transcoder-transcriber
A cloud transcoder for videos that features transcribing capabilities. Built for CPSC 454 - Cloud Security at CSUF.

## What works now

Login uses Amazon Cognito and files are stored in S3; encoding and transcription still run inside the API.

1. On the **Encode** tab, pick an MP4, choose settings, and optionally ask for a transcript.
2. The browser uploads the video straight to S3; the API then encodes it with FFmpeg, transcribes it with faster-whisper, and saves the results to S3.
3. The **Library** tab lists your jobs (queued, processing, ready or failed) with buttons to download the encoded video, the transcript (JSON with the full text and timestamped segments) and subtitles (SRT).

Uploads are deleted after 1 day and results after 7. Job info is in `local_data/app.sqlite3` (gitignored).

You must log in to encode or see jobs, and each user only sees their own. Login happens on Cognito's pages, so the app never handles passwords; see [docs/aws-resources.md](docs/aws-resources.md).

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/), Node.js, and FFmpeg on your PATH (`brew install ffmpeg` / `apt install ffmpeg`).

Terminal 1, from the project root (API at http://localhost:8000, docs at http://localhost:8000/docs):

```bash
uv sync
cp .env.example .env    # then paste the Cognito client secret and set AWS_PROFILE in .env
aws login --profile my-profile   # S3 needs a current AWS login (see AWS setup)
uv run uvicorn api.main:app --reload --reload-dir api --reload-dir worker
```

Use this command, not `fastapi dev`: that one also watches `.venv/`, and a restart kills any running job.

Terminal 2:

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173
```

Then open http://localhost:5173, click **Sign up** (you'll need an authenticator app for MFA), encode a video, and find it in the Library. The Library doesn't refresh on its own, so reload it to see a job's status change.

The first transcript downloads the Whisper model. The default `medium.en` is about 1.5 GB and slow on a CPU; for quicker local runs prefix the API command with `WHISPER_MODEL=base` (or `tiny`).

## AWS setup

Only login uses AWS (Cognito) so far, but you can connect and check access to the bucket and queues now. Ask for an IAM user in the team account (`850870347029`) with the `SignInLocalDevelopmentAccess` policy. Don't use access keys or root.

In the commands below, replace **`my-profile`** with your own AWS CLI profile name, meaning whatever you pass to `aws login --profile`. `aws configure list-profiles` shows your profiles. If you signed in without `--profile`, use `default`.

First, sign in. When asked for a region, enter `us-east-1`, then approve in the browser as your IAM user:

```bash
aws login --profile my-profile
```

Then run the check. It's read-only. It should print your user, `credentials: login`, the bucket and the queue, with no `WARNING` lines.

macOS / Linux:

```bash
AWS_PROFILE=my-profile S3_BUCKET=transcoding-titans-media-850870347029-us-east-1-an \
  SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/850870347029/transcoding-titans-jobs \
  uv run python scripts/check_aws.py
```

Windows (cmd). The `set` values last until you close the window:

```bat
set AWS_PROFILE=my-profile
set S3_BUCKET=transcoding-titans-media-850870347029-us-east-1-an
set SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/850870347029/transcoding-titans-jobs
uv run python scripts\check_aws.py
```

Windows (PowerShell). The `$env:` values last until you close the window:

```powershell
$env:AWS_PROFILE = "my-profile"
$env:S3_BUCKET = "transcoding-titans-media-850870347029-us-east-1-an"
$env:SQS_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/850870347029/transcoding-titans-jobs"
uv run python scripts\check_aws.py
```

Sessions last up to 12 hours; run `aws login --profile my-profile` again after that. The bucket and queues, their settings, and the rules for code that uses them are in [docs/aws-resources.md](docs/aws-resources.md).

## Backend

```
api/
  main.py                  FastAPI app, CORS, /health
  auth.py                  Cognito login (/auth/*), session cookies, current_user
  jobs.py                  upload, job, list and download routes; runs jobs one at a time on a background thread
  db.py                    SQLite tables for users, sessions, uploads and jobs
  schemas.py               request/response models (mirror frontend/src/api/types.ts)
  config.py                settings, overridable with env vars
worker/
  Ffmpeg_script.py         runFfmpeg() encodes a video; probeVideo() checks an upload first
  faster_whisper_script.py run_faster_whisper() writes a JSON transcript and SRT subtitles
  converter.py             old JSON -> SRT converter (superseded)
```

The API maps the frontend's setting keys (e.g. `'720p'`, `'h264'`) to FFmpeg values from its own whitelist, then calls the worker functions. Later, these functions move to EC2 workers fed by SQS, and `local_data/` is replaced by S3.

To test the FFmpeg script on its own, put a video in `videos_un/` and run `uv run python worker/Ffmpeg_script.py` (output goes to `videos_pro/`).

## Frontend (React + Vite)

Other scripts: `npm run build` (type-checks, then builds) and `npm run lint`.

### What's there

- **Encode tab:** pick an MP4 (click or drag it in), choose a Low, Medium, High or Custom preset, adjust individual settings, and optionally request a transcript.
- **Library tab:** your past jobs with their status, expiry date, and download buttons for the video, transcript and subtitles. The expiry date is a label for now; local files aren't deleted automatically.
- **Log in / Sign up:** buttons in the top bar go to Cognito's login page, which sends you back to the Library logged in.

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
  components/        top bar, select field
  dev/               dev-only helpers (mock API, FFmpeg command preview)
  styles/global.css  colors, fonts and shared styles
```

### Connecting to the backend

All endpoint paths are in `src/config/api.ts`, and all request and response shapes are in `src/api/types.ts`. The FastAPI models use the same names and fields, in camelCase JSON.

Each feature has a flag in `API_CONNECTED`. Both `auth` and `jobs` are `true`, so the app uses the real API.

The API address defaults to `http://localhost:8000`. To change it, copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL`. Anything starting with `VITE_` ends up in the public JavaScript, so never put secrets there.

### Dev-only extras

In `npm run dev`, the Encode page shows the FFmpeg command your settings would produce, with a copy button. It and the mock API are left out of production builds.

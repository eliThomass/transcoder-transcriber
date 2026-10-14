# CLAUDE.md

This file guides Claude Code (claude.ai/code) when it works in this repository.

## Project

A web app for cloud video transcoding and transcription, built as a group project for CPSC 454 (Cloud Security) at CSUF. Users upload videos through a React frontend. A FastAPI service works with AWS to run the jobs: FFmpeg does the transcoding and faster-whisper does the transcription on EC2 workers. Results are kept in S3 for a limited time so users can view or download them.

**This is a cloud security course.** Security choices (IAM, least privilege, private buckets, input handling) are part of what is graded, not an afterthought. When you add AWS or upload code, prefer the secure option and say why.

## Current state (basic local pipeline; AWS not wired yet)

This branch keeps only the essentials: upload a video, encode and transcribe it, save the results locally, list jobs and download them. A fuller version (auth, signed URLs, SQS-style queue and separate worker process, tests) is saved on the `feat/full-local-backend` branch. Check the code before assuming a piece exists.

- `api/`: FastAPI app. No auth yet, so every job is visible to everyone.
  - `config.py`: env-driven settings (`DATA_DIR`, `MAX_UPLOAD_BYTES`, `CORS_ORIGINS`, ...).
  - `db.py`: SQLite (`local_data/app.sqlite3`) with `uploads` and `jobs` tables.
  - `schemas.py`: Pydantic mirror of the parts of `frontend/src/api/types.ts` in use. Keep the two in sync.
  - `jobs.py`: `POST /uploads`, `POST /uploads/{id}/file` (stand-in for the browser's direct S3 upload), `POST /jobs`, `GET /jobs`, `GET /jobs/{id}/download` and `GET /jobs/{id}/files/{file}`. Jobs run one at a time on a background thread inside the API.
  - Files are saved under `local_data/storage/` using the planned S3 keys (`uploads/<uploadId>.mp4`, `outputs/<jobId>/video_<res>.mp4`, `outputs/<jobId>/transcript.txt`).
- `worker/`: plain functions the API calls, ready to move to an EC2 worker. `transcode.py` (ffprobe check + whitelisted FFmpeg arguments; forces `-f mp4 -protocol_whitelist file`) and `transcribe.py` (faster-whisper; writes a plain `.txt` transcript).
- Not implemented yet: `/auth/*`, `GET /jobs/{id}`, `DELETE /jobs/{id}`, expiry cleanup and tests.
- `frontend/`: React 19 + Vite + TypeScript. `App.tsx` renders a top bar (`components/TopBar.tsx`) with **Encode** and **Library** tabs and Log in / Sign up buttons, and opens `components/AuthDialog.tsx` (a native `<dialog>`) for login and signup. Tabs use the URL hash (`#/encode`, `#/library`; see `config/navigation.ts`), not a router library. The logged-in `user` state lives in `App.tsx`.
  - `src/pages/UploadPage.tsx` (Encode tab): MP4 file picker, Low/Medium/High/Custom preset, and dropdowns for each FFmpeg option. Submit calls `startEncode()` (see below). The file picker is a 16:9 "monitor" drop zone (click or drag-and-drop) with SMPTE color bars.
  - `src/pages/LibraryPage.tsx` (Library tab): when logged out, a prompt to log in. When logged in, the user's jobs with status (queued / processing / ready / failed), expiry, and buttons to download the video and the transcript.
  - Styling is plain CSS with BEM-style class names (`upload-form__section`, `field__label`, ...). `src/styles/global.css` holds the design tokens (CSS variables), base styles, and the shared `.page`, `.button` and `.field` styles. Each page or component imports its own stylesheet next to it (e.g. `UploadPage.css`). The look: cool grey "paper", graphite ink, a single blue accent (`--accent`) and the Archivo variable font from Google Fonts, which uses `font-stretch` for width. Avoid generic template looks (cards with shadows, gradients, all-caps labels).
  - `src/config/transcodeOptions.ts` defines every dropdown's options, the `TranscodeSettings` type and the preset values. Option values are short keys (`'h264'`, `'720p'`), not FFmpeg flags. The API must map them to arguments from its own whitelist.
  - `src/components/SelectField.tsx` is the reusable labelled `<select>`.
  - `src/dev/FfmpegCommandPreview.tsx` shows the FFmpeg command for the current settings, rendered only when `import.meta.env.DEV` is true (it is stripped from production builds). Keep dev-only tools in `src/dev/`. Its key → flag mapping is for display only; the backend owns the real one.
- There are no tests, no Python linter config and no infrastructure-as-code yet.

### Connecting the frontend to the API

All backend calls go through a small layer, so pages and components never call `fetch` directly:

- `src/config/api.ts`:
  - `API_BASE_URL` comes from `VITE_API_BASE_URL` (see `frontend/.env.example`) and defaults to `http://localhost:8000`.
  - `API_ROUTES` lists every endpoint path the frontend expects, with its method and response shape in comments.
  - `API_CONNECTED` holds one flag per feature (`auth`, `jobs`; `jobs` also covers `/uploads`).
- `src/api/types.ts`: **the API contract.** Every request and response type, plus the worker message types. The Pydantic models must mirror it; the conventions are at the top of the file.
- `src/api/client.ts`: `apiFetch()` sends JSON with `credentials: 'include'` and turns FastAPI `{ "detail": ... }` errors into `ApiError`.
- `src/api/health.ts`: `checkHealth`.
- `src/auth/authApi.ts`: `signUp`, `logIn`, `logOut` and `getCurrentUser`.
- `src/jobs/jobsApi.ts`: `createUpload`, `uploadToS3`, `createJob`, `startEncode` (runs those three in order), `listJobs`, `getJob`, `deleteJob` and `getDownloadLink`. `getDownloadLink` rejects any URL that isn't `https:` before the page navigates to it (dev builds also allow `http://localhost` for the local API).

While a flag in `API_CONNECTED` is false, its functions return mock data from `src/dev/mockApi.ts` in `npm run dev` (any email and password logs in) and a "not available yet" error in production builds. To connect a feature:

1. Build the FastAPI endpoints to match `API_ROUTES` and the TypeScript types.
2. Flip the flag to `true`.

Backend contract notes:

- **Sessions:** use an **httpOnly, Secure, SameSite cookie** set by the API. Never store tokens in `localStorage`.
- **CORS:** FastAPI needs CORS with `allow_credentials=True` and an explicit origin list (e.g. `http://localhost:5173`), not `*`.
- **JSON field names:** return camelCase JSON (e.g. Pydantic `alias_generator=to_camel`) so it matches `src/api/types.ts`.
- **Downloads:** the API returns a short-lived presigned S3 GET URL (`{ "url": ... }`) with `Content-Disposition: attachment`. It must check that the video belongs to the logged-in user before signing.
- **Expiry:** `expiresAt` should match the S3 lifecycle rule, so the UI's "Expires in N days" is accurate.

### API contract

Types are in `frontend/src/api/types.ts`; paths are in `frontend/src/config/api.ts`. Every endpoint except `/health` and signup/login requires the session cookie and acts only on the logged-in user's own data. The user id always comes from the session, never from the request.

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/health` | | `HealthResponse` |
| POST | `/auth/signup` | `Credentials` | `User` (201) + session cookie |
| POST | `/auth/login` | `Credentials` | `User` + session cookie |
| POST | `/auth/logout` | | 204, clears cookie |
| GET | `/auth/me` | | `User`, or 401 |
| POST | `/uploads` | `CreateUploadRequest` | `UploadTicket` (201): presigned S3 POST |
| POST | `/jobs` | `CreateJobRequest` | `Job` (202) |
| GET | `/jobs` | | `Job[]`, newest first |
| GET | `/jobs/{jobId}` | | `Job` |
| DELETE | `/jobs/{jobId}` | | 204; deletes the job's S3 files early |
| GET | `/jobs/{jobId}/download?file=video\|transcript` | | `DownloadLink` |

The encode flow:

1. `POST /uploads` returns a presigned S3 POST, whose policy enforces the size limit and the `video/mp4` content type.
2. The browser uploads the file straight to S3.
3. `POST /jobs` validates the settings (Literal types), records the job, and enqueues a `WorkerJobMessage` on SQS. If needed, it also launches or scales EC2 workers.

**Workers are only ever started as a side effect of `POST /jobs`.** There is no public "start worker" endpoint, so users never control infrastructure directly.

Worker messages:

- **`WorkerJobMessage`** (API → SQS → worker) carries everything a worker needs: `jobId`, `userId`, `inputKey`, `outputPrefix`, `settings`, `transcribe`, and `schemaVersion` for future changes.
- **The bucket and queue names come from the worker's environment, not the message**, so a forged message can't point a worker at another bucket.
- **`WorkerJobStarted` and `WorkerJobResult`** are what a worker reports back. Whether that goes through a direct DynamoDB update or a result queue is still open.

## Commands

Python backend (run from the repo root; uses **uv**):

```bash
uv sync                                   # install deps into .venv
uv run fastapi dev api/main.py            # dev server at http://localhost:8000 (auto-reload)
uv add <pkg>                              # add a dependency (updates pyproject.toml + uv.lock)
uv export --format requirements-txt > requirements.txt   # regenerate after dep changes
```

`requirements.txt` is generated by `uv export`. Do not edit it by hand. Regenerate it whenever `pyproject.toml` changes so that pip users stay in sync.

Frontend (run from `frontend/`):

```bash
npm install
npm run dev       # http://localhost:5173
npm run build     # tsc -b && vite build (type-checks first)
npm run lint      # eslint
```

The root `.gitignore` is the Python template, and its `lib/` rule also ignores `frontend/src/lib/`. Don't put frontend source in a folder named `lib`.

The frontend uses the React Compiler (`babel-plugin-react-compiler` via `@rolldown/plugin-babel` in `vite.config.ts`), so manual `useMemo` and `useCallback` are usually unnecessary. `tsconfig.app.json` enables `noUnusedLocals`, `noUnusedParameters`, `verbatimModuleSyntax` (use `import type` for type-only imports) and `erasableSyntaxOnly` (no `enum` and no parameter properties).

System dependency: **FFmpeg** must be installed on the machine (`brew install ffmpeg` / `apt install ffmpeg`). It is not a pip package. The repo pins Python **3.12** (`.python-version`, `requires-python >=3.12`).

## Planned architecture

```
React (upload UI)
  → FastAPI: auth, validate request, issue presigned S3 PUT URL
  → browser uploads directly to S3  (uploads/<jobId>/<file>)
  → FastAPI sends job message to SQS
  → EC2 worker(s) long-poll SQS, download input from S3
  → run FFmpeg (transcode renditions / thumbnail) and faster-whisper (transcript)
  → upload outputs to S3 (outputs/<jobId>/...), delete SQS message
  → FastAPI reports job status; frontend fetches results via presigned GET URLs
```

Example SQS job message:

```json
{ "jobId": "abc123", "inputKey": "uploads/video123.mp4", "outputs": ["1080p", "720p", "480p"] }
```

The storage backend for job/user metadata (DynamoDB, RDS, etc.) has not been chosen.

### AWS conventions and security rules

- **Never commit AWS credentials** or `.env` files (`.env` is already gitignored). Developers authenticate with IAM Identity Center / `aws sso login` profiles. Code should rely on the default boto3 credential chain and never hard-code keys.
- **Workers use an IAM role (EC2 instance profile)**, never access keys. Each role follows least privilege and is scoped to specific ARNs and prefixes. For example, a worker may `s3:GetObject` on `uploads/*`, `s3:PutObject` on `outputs/*`, and receive/delete messages on one queue only.
- **S3 stays private.** Block Public Access stays on. Users reach objects only through **short-lived presigned URLs** generated by the API. Do not use public object URLs or `public-read` ACLs.
- **Retention** ("store for some time") should use S3 lifecycle expiration rules, not cron cleanup code.
- **SQS**: standard queues deliver at least once, so workers must be **idempotent**, meaning reprocessing the same `jobId` must be safe. The visibility timeout must exceed the worst-case job duration, or the worker must extend it while running. Configure a **dead-letter queue**. Workers should use long polling (`WaitTimeSeconds=20`).
- **Uploads are untrusted input.** Enforce size limits (for example with presigned POST conditions), validate the container and codec with `ffprobe` before processing, and generate object keys server-side (`uploads/<uuid>/...`) instead of trusting user filenames.

### FFmpeg usage

- Invoke FFmpeg with `subprocess.run([...])` and an **argument list**. Never use `shell=True` or string-interpolated commands, because filenames and options come from users and would allow command injection. Whitelist allowed resolutions, codecs and presets rather than passing user values through.
- **Supported codecs for now: H.264 video (`libx264`) and MP3 audio (`libmp3lame`) in MP4.** Don't add other codecs unless asked. Audio bitrate is not a user option; the AWS worker chooses it.
- Baseline rendition command (30 fps, CRF 23, `medium` preset):

  ```bash
  ffmpeg -i input.mp4 -vf "scale=-2:720" -r 30 -c:v libx264 -preset medium -crf 23 -c:a libmp3lame output_720p.mp4
  ```

  Renditions: 1080p, 720p, 480p. `scale=-2:<height>` keeps the aspect ratio (and an even width), so vertical videos are not stretched. Fixed `scale=1280:720` would distort them.
- Brightness adjustment uses `-vf "eq=brightness=0.1"`. Thumbnails can be produced with a single-frame extract such as `-ss <t> -frames:v 1 thumb.jpg`.
- Codec tradeoffs: H.264 is the most compatible and cheapest to encode. H.265/HEVC gives about 50% better compression but costs more to encode. AV1 compresses best but is the slowest and least supported. For audio, AAC is the default for MP4.

### Transcription

- Use `faster-whisper` (CTranslate2 backend; pulls in `av`, so it does not need the FFmpeg binary to decode audio). Model size and `compute_type` (for example `int8` on CPU instances) drive EC2 instance sizing and cost.

## Open design questions

Ask rather than assume on these:

- Which input containers are accepted: MP4 only, or MKV, MOV and others?
- How vertical and odd-aspect videos should be handled in renditions.
- Where job and user metadata live, and how users authenticate. The team floated storing user login info in S3. Push back on that: S3 is object storage, not a user database. It has no atomic "is this email taken" check and no per-record access control, and it would mean hand-rolling password hashing. Prefer **Amazon Cognito** (it handles password hashing, MFA and lockout). Failing that, use DynamoDB with passwords hashed by argon2 or bcrypt. S3 remains the right place for the videos themselves.
- Whether the project uses a single shared AWS account with IAM Identity Center users/groups (leaning this way, since it avoids cross-account permissions) or three accounts under an AWS Organization.
- Whether workers are always-on EC2, auto-scaled on queue depth, or launched per job by the API.
- Optional features: thumbnails (first frame, random frame, or preview clip) and output format conversion.

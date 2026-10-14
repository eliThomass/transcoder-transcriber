# transcoder-transcriber
A cloud transcoder for videos that features transcribing capabilities. Built for CPSC 454 - Cloud Security at CSUF.

## Backend (FastAPI)

From the project root:

```bash
uv sync
uv run fastapi dev api/main.py     # API at http://localhost:8000 (docs at /docs)
```

Requires FFmpeg on your PATH (`brew install ffmpeg`). The first transcript downloads the Whisper model (~150 MB for `base`; set `WHISPER_MODEL=tiny` for a faster one).

Everything is local for now. Uploaded videos, encoded outputs and transcripts are saved in `local_data/storage/`, and job info is in `local_data/app.sqlite3` (both gitignored). Encoding and transcription run inside the API process, one job at a time.

**No access control yet:** there are no accounts, so anyone who can reach the API can upload files and see or download every job. Only run it on your own machine (`fastapi dev` listens on `127.0.0.1` by default).

## Frontend (React + Vite)

From the `frontend` directory:

```bash
cd frontend
npm install
npm run dev
```

The app will be available at http://localhost:5173.

Other scripts: `npm run build` (type-checks, then builds) and `npm run lint`.

### What's there

- **Encode tab:** pick an MP4 (click or drag it in), choose a Low, Medium, High or Custom preset, adjust individual settings, and optionally request a transcript.
- **Library tab:** your past jobs with their status, expiry date, and download buttons for the video and transcript.
- **Log in / Sign up:** buttons in the top bar open a dialog.

Only MP4 input, H.264 video and MP3 audio are supported for now.

### Layout

```
frontend/src/
  api/types.ts       request/response types (the API contract)
  api/client.ts      fetch wrapper used by every API call
  auth/authApi.ts    sign up, log in, log out, current user
  jobs/jobsApi.ts    upload to S3, create/list/delete jobs, download links
  config/            API routes and flags, encode options and presets, tabs
  pages/             Encode (UploadPage) and Library pages
  components/        top bar, login dialog, select field
  dev/               dev-only helpers (mock API, FFmpeg command preview)
  styles/global.css  colors, fonts and shared styles
```

### Connecting to the backend

Encoding and the Library are connected to the API (`API_CONNECTED.jobs` is `true`). Accounts aren't built yet, so `auth` stays `false` and dev mode logs in with mock data. All endpoint paths are in `src/config/api.ts`, and all request and response shapes are in `src/api/types.ts`. The FastAPI models should use the same names and fields, in camelCase JSON.

Each feature has a flag in `API_CONNECTED` (`auth` and `jobs`). While a flag is `false`:

- `npm run dev` uses fake data from `src/dev/mockApi.ts`. Any email and password logs in, and the library shows sample jobs.
- A production build shows "not available yet" instead.

Once the matching endpoints exist, set the flag to `true`.

The API address defaults to `http://localhost:8000`. To change it, copy `.env.example` to `.env.local` and set `VITE_API_BASE_URL`. Anything starting with `VITE_` ends up in the public JavaScript, so never put secrets there.

### Dev-only extras

In `npm run dev`, the Encode page shows the FFmpeg command your settings would produce, with a copy button. It and the mock API are left out of production builds.

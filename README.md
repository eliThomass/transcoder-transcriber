# transcoder-transcriber
A cloud transcoder for videos that features transcribing capabilities. Built for CPSC 454 - Cloud Security at CSUF.

## Backend (FastAPI)

From the project root:

```bash
uv sync
uv run fastapi dev api/main.py --reload
```

Or run (without uv):

```bash
uvicorn api.main:app --reload
```

The API will be available at http://localhost:8000.

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

The frontend is ready for the API but isn't connected yet. All endpoint paths are in `src/config/api.ts`, and all request and response shapes are in `src/api/types.ts`. The FastAPI models should use the same names and fields, in camelCase JSON.

Each feature has a flag in `API_CONNECTED` (`auth` and `jobs`). While a flag is `false`:

- `npm run dev` uses fake data from `src/dev/mockApi.ts`. Any email and password logs in, and the library shows sample jobs.
- A production build shows "not available yet" instead.

Once the matching endpoints exist, set the flag to `true`.

The API address defaults to `http://localhost:8000`. To change it, copy `.env.example` to `.env.local` and set `VITE_API_BASE_URL`. Anything starting with `VITE_` ends up in the public JavaScript, so never put secrets there.

### Dev-only extras

In `npm run dev`, the Encode page shows the FFmpeg command your settings would produce, with a copy button. It and the mock API are left out of production builds.

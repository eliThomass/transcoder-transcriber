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

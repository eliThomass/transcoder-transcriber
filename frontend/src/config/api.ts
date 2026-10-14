// Where the FastAPI backend lives. Override it in frontend/.env.local.
// Anything prefixed VITE_ is bundled into the public JS, so never put secrets here.
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

// Flip a flag to true once its FastAPI endpoints exist. While a flag is false,
// its API functions return mock data in `npm run dev` (see src/dev/mockApi.ts)
// and a "not available yet" error in production builds.
export const API_CONNECTED: { auth: boolean; jobs: boolean } = {
  auth: false,
  jobs: false, // covers /uploads and /jobs/*
}

// Every endpoint the frontend expects. Request and response types are in
// src/api/types.ts. Keep in sync with api/main.py.
export const API_ROUTES = {
  health: '/health', // GET -> HealthResponse

  auth: {
    signUp: '/auth/signup', // POST Credentials -> User (201), sets the session cookie
    logIn: '/auth/login', // POST Credentials -> User, sets the session cookie
    logOut: '/auth/logout', // POST -> 204, clears the session cookie
    currentUser: '/auth/me', // GET -> User, or 401 when logged out
  },

  uploads: {
    create: '/uploads', // POST CreateUploadRequest -> UploadTicket (201)
  },

  jobs: {
    create: '/jobs', // POST CreateJobRequest -> Job (202); enqueues work for the EC2 workers
    list: '/jobs', // GET -> Job[] for the logged-in user, newest first
    // GET -> Job; DELETE -> 204 (deletes the job and its S3 files early)
    detail: (jobId: string) => `/jobs/${encodeURIComponent(jobId)}`,
    // GET -> DownloadLink
    download: (jobId: string, file: 'video' | 'transcript') =>
      `/jobs/${encodeURIComponent(jobId)}/download?file=${file}`,
  },
} as const

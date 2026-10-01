// Where the FastAPI backend lives. Override it in frontend/.env.local.
// Anything prefixed VITE_ is bundled into the public JS, so never put secrets here.
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

// Flip a flag to true once its FastAPI endpoints exist. While a flag is false,
// its API functions return mock data in `npm run dev` (see src/dev/mockApi.ts)
// and a "not available yet" error in production builds.
export const API_CONNECTED: { auth: boolean; library: boolean } = {
  auth: false,
  library: false,
}

// Endpoint paths the frontend expects. Keep in sync with api/main.py.
export const API_ROUTES = {
  auth: {
    logIn: '/auth/login', // POST { email, password } -> User, sets the session cookie
    signUp: '/auth/signup', // POST { email, password } -> User, sets the session cookie
    logOut: '/auth/logout', // POST -> 204, clears the session cookie
    currentUser: '/auth/me', // GET -> User, or 401 when logged out
  },
  library: {
    list: '/videos', // GET -> LibraryVideo[] for the logged-in user
    // GET -> { url }: a short-lived presigned S3 URL for the file
    download: (videoId: string, file: 'video' | 'transcript') =>
      `/videos/${encodeURIComponent(videoId)}/download?file=${file}`,
  },
} as const

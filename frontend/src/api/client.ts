import { API_BASE_URL } from '../config/api.ts'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// Returned by API functions whose backend endpoint isn't built yet.
export function notConnected(message: string): Promise<never> {
  return Promise.reject(new Error(message))
}

// FastAPI error bodies look like { "detail": "..." }.
async function readErrorMessage(response: Response) {
  try {
    const body: unknown = await response.json()
    if (
      body &&
      typeof body === 'object' &&
      'detail' in body &&
      typeof body.detail === 'string'
    ) {
      return body.detail
    }
  } catch {
    // Not JSON; fall through to the generic message.
  }
  return `Request failed (${response.status}).`
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    // The session is an httpOnly cookie set by the API, so JavaScript never
    // touches the token. Don't store tokens in localStorage.
    credentials: 'include',
  })

  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Something went wrong. Try again.'
}

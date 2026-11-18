import { ApiError, apiFetch } from '../api/client.ts'
import type { LogoutResponse, User } from '../api/types.ts'
import { API_BASE_URL, API_CONNECTED, API_ROUTES } from '../config/api.ts'

// Login and sign-up happen on Cognito's pages, so these are full page navigations, not fetches.
// The API redirects to Cognito, then back to the Library with a session cookie.
export function logIn(): void {
  window.location.assign(`${API_BASE_URL}${API_ROUTES.auth.logIn}`)
}

export function signUp(): void {
  window.location.assign(`${API_BASE_URL}${API_ROUTES.auth.signUp}`)
}

// Ends the API session, then visits Cognito's logout page to end the Cognito login too.
export async function logOut(): Promise<void> {
  const { url } = await apiFetch<LogoutResponse>(API_ROUTES.auth.logOut, { method: 'POST' })
  if (new URL(url).protocol !== 'https:') throw new Error('Unexpected logout URL.')
  window.location.assign(url)
}

// Restores the session on page load. Resolves to null when nobody is logged in.
export async function getCurrentUser(): Promise<User | null> {
  if (!API_CONNECTED.auth) return null
  try {
    return await apiFetch<User>(API_ROUTES.auth.currentUser)
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}

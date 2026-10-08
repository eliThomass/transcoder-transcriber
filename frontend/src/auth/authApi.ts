import { ApiError, apiFetch, notConnected } from '../api/client.ts'
import type { Credentials, User } from '../api/types.ts'
import { API_CONNECTED, API_ROUTES } from '../config/api.ts'
import { mockLogIn, mockSignUp } from '../dev/mockApi.ts'

/** Which form the auth dialog shows. UI-only; not part of the API contract. */
export type AuthMode = 'logIn' | 'signUp'

const NOT_CONNECTED_MESSAGE = "Accounts aren't available yet."

export function signUp(credentials: Credentials): Promise<User> {
  if (!API_CONNECTED.auth) {
    return import.meta.env.DEV
      ? mockSignUp(credentials)
      : notConnected(NOT_CONNECTED_MESSAGE)
  }
  return apiFetch<User>(API_ROUTES.auth.signUp, {
    method: 'POST',
    body: JSON.stringify(credentials),
  })
}

export function logIn(credentials: Credentials): Promise<User> {
  if (!API_CONNECTED.auth) {
    return import.meta.env.DEV
      ? mockLogIn(credentials)
      : notConnected(NOT_CONNECTED_MESSAGE)
  }
  return apiFetch<User>(API_ROUTES.auth.logIn, {
    method: 'POST',
    body: JSON.stringify(credentials),
  })
}

export async function logOut(): Promise<void> {
  if (!API_CONNECTED.auth) return
  await apiFetch<void>(API_ROUTES.auth.logOut, { method: 'POST' })
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

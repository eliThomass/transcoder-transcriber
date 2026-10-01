// Dev-only fake API responses so the UI can be clicked through before the
// backend exists. Only reached through `import.meta.env.DEV` branches, so
// production builds drop this file. Any email and password "logs in".

import type { Credentials, User } from '../auth/authApi.ts'
import type { LibraryVideo } from '../library/libraryApi.ts'

const DAY_MS = 24 * 60 * 60 * 1000

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function daysFromNow(days: number) {
  return new Date(Date.now() + days * DAY_MS).toISOString()
}

export async function mockLogIn({ email }: Credentials): Promise<User> {
  await delay(400)
  return { id: 'dev-user', email }
}

export const mockSignUp = mockLogIn

export async function mockFetchLibrary(): Promise<LibraryVideo[]> {
  await delay(500)
  return [
    {
      id: 'vid-1',
      fileName: 'lecture-week-5.mp4',
      status: 'processing',
      resolution: '1080p',
      createdAt: daysFromNow(0),
      expiresAt: daysFromNow(7),
      sizeBytes: null,
      hasTranscript: true,
    },
    {
      id: 'vid-2',
      fileName: 'group-demo-final.mp4',
      status: 'ready',
      resolution: '720p',
      createdAt: daysFromNow(-1),
      expiresAt: daysFromNow(6),
      sizeBytes: 48_300_000,
      hasTranscript: true,
    },
    {
      id: 'vid-3',
      fileName: 'screen-recording 2026-09-24.mp4',
      status: 'ready',
      resolution: '480p',
      createdAt: daysFromNow(-5),
      expiresAt: daysFromNow(2),
      sizeBytes: 12_900_000,
      hasTranscript: false,
    },
    {
      id: 'vid-4',
      fileName: 'interview-raw.mp4',
      status: 'failed',
      resolution: '1080p',
      createdAt: daysFromNow(-6),
      expiresAt: daysFromNow(1),
      sizeBytes: null,
      hasTranscript: false,
    },
  ]
}

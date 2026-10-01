import { apiFetch, notConnected } from '../api/client.ts'
import { API_CONNECTED, API_ROUTES } from '../config/api.ts'
import type { TranscodeSettings } from '../config/transcodeOptions.ts'
import { mockFetchLibrary } from '../dev/mockApi.ts'

export type VideoStatus = 'processing' | 'ready' | 'failed'

export type DownloadFile = 'video' | 'transcript'

// The shape the API should return for each video (camelCase JSON).
export type LibraryVideo = {
  id: string
  fileName: string
  status: VideoStatus
  resolution: TranscodeSettings['resolution']
  createdAt: string // ISO 8601
  expiresAt: string // ISO 8601: when the S3 lifecycle rule deletes it
  sizeBytes: number | null // null until the encode finishes
  hasTranscript: boolean
}

export function fetchLibrary(): Promise<LibraryVideo[]> {
  if (!API_CONNECTED.library) {
    return import.meta.env.DEV
      ? mockFetchLibrary()
      : notConnected("The library isn't available yet.")
  }
  return apiFetch<LibraryVideo[]>(API_ROUTES.library.list)
}

// Asks the API for a short-lived presigned S3 URL for one file.
export async function getDownloadUrl(
  videoId: string,
  file: DownloadFile,
): Promise<string> {
  if (!API_CONNECTED.library) {
    return notConnected("Downloads aren't available yet.")
  }
  const { url } = await apiFetch<{ url: string }>(
    API_ROUTES.library.download(videoId, file),
  )
  return url
}

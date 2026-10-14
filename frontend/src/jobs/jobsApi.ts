import { apiFetch, notConnected } from '../api/client.ts'
import type {
  CreateJobRequest,
  CreateUploadRequest,
  DownloadFile,
  DownloadLink,
  Job,
  TranscodeSettings,
  UploadTicket,
} from '../api/types.ts'
import { API_CONNECTED, API_ROUTES } from '../config/api.ts'
import { mockListJobs, mockStartEncode } from '../dev/mockApi.ts'

const NOT_CONNECTED_MESSAGE = "Encoding isn't available yet."

// Step 1: ask the API for a presigned S3 POST for this file.
export function createUpload(request: CreateUploadRequest): Promise<UploadTicket> {
  if (!API_CONNECTED.jobs) return notConnected(NOT_CONNECTED_MESSAGE)
  return apiFetch<UploadTicket>(API_ROUTES.uploads.create, {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

// Step 2: send the file straight to S3. This goes to S3, not our API, so it
// doesn't use apiFetch and sends no cookies.
export async function uploadToS3(ticket: UploadTicket, file: File): Promise<void> {
  if (file.size > ticket.maxSizeBytes) {
    throw new Error('This file is larger than the upload limit.')
  }

  const form = new FormData()
  for (const [name, value] of Object.entries(ticket.fields)) {
    form.append(name, value)
  }
  form.append('file', file) // S3 requires the file to be the last field

  const response = await fetch(ticket.url, { method: 'POST', body: form })
  if (!response.ok) {
    throw new Error('The upload failed. Try again.')
  }
}

// Step 3: create the job. The API enqueues it for the EC2 workers.
export function createJob(request: CreateJobRequest): Promise<Job> {
  if (!API_CONNECTED.jobs) return notConnected(NOT_CONNECTED_MESSAGE)
  return apiFetch<Job>(API_ROUTES.jobs.create, {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

// Runs steps 1–3 for the Encode page.
export async function startEncode(
  file: File,
  settings: TranscodeSettings,
  transcribe: boolean,
): Promise<Job> {
  if (!API_CONNECTED.jobs) {
    return import.meta.env.DEV
      ? mockStartEncode(file, settings, transcribe)
      : notConnected(NOT_CONNECTED_MESSAGE)
  }

  const ticket = await createUpload({
    fileName: file.name,
    contentType: 'video/mp4',
    sizeBytes: file.size,
  })
  await uploadToS3(ticket, file)
  return createJob({ uploadId: ticket.uploadId, settings, transcribe })
}

export function listJobs(): Promise<Job[]> {
  if (!API_CONNECTED.jobs) {
    return import.meta.env.DEV
      ? mockListJobs()
      : notConnected("The library isn't available yet.")
  }
  return apiFetch<Job[]>(API_ROUTES.jobs.list)
}

export function getJob(jobId: string): Promise<Job> {
  if (!API_CONNECTED.jobs) return notConnected(NOT_CONNECTED_MESSAGE)
  return apiFetch<Job>(API_ROUTES.jobs.detail(jobId))
}

export async function deleteJob(jobId: string): Promise<void> {
  if (!API_CONNECTED.jobs) return notConnected(NOT_CONNECTED_MESSAGE)
  await apiFetch<void>(API_ROUTES.jobs.detail(jobId), { method: 'DELETE' })
}

// Asks the API for a short-lived presigned S3 URL for one output file.
export async function getDownloadLink(
  jobId: string,
  file: DownloadFile,
): Promise<DownloadLink> {
  if (!API_CONNECTED.jobs) return notConnected("Downloads aren't available yet.")
  const link = await apiFetch<DownloadLink>(API_ROUTES.jobs.download(jobId, file))

  // The page navigates to this URL, so refuse anything but https
  // (e.g. a javascript: URL from a compromised or misconfigured API).
  if (new URL(link.url).protocol !== 'https:') {
    throw new Error('The download link was invalid.')
  }
  return link
}

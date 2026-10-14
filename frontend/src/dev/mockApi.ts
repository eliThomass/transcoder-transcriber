// Dev-only fake API responses so the UI can be clicked through before the
// backend exists. Only reached through `import.meta.env.DEV` branches, so
// production builds drop this file. Any email and password "logs in".

import type { Credentials, Job, TranscodeSettings, User } from '../api/types.ts'
import { QUALITY_PRESETS } from '../config/transcodeOptions.ts'

const DAY_MS = 24 * 60 * 60 * 1000
const RETENTION_DAYS = 7

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function daysFromNow(days: number) {
  return new Date(Date.now() + days * DAY_MS).toISOString()
}

export async function mockLogIn({ email }: Credentials): Promise<User> {
  await delay(400)
  return { id: 'dev-user', email, createdAt: daysFromNow(-30) }
}

export const mockSignUp = mockLogIn

export async function mockStartEncode(
  file: File,
  settings: TranscodeSettings,
  transcribe: boolean,
): Promise<Job> {
  await delay(800)
  const now = daysFromNow(0)
  return {
    id: `dev-job-${Date.now()}`,
    status: 'queued',
    fileName: file.name,
    settings,
    transcribe,
    createdAt: now,
    updatedAt: now,
    expiresAt: daysFromNow(RETENTION_DAYS),
    outputSizeBytes: null,
    hasTranscript: false,
    error: null,
  }
}

function mockJob(
  overrides: Pick<Job, 'id' | 'status' | 'fileName'> & Partial<Job>,
  ageDays: number,
): Job {
  const createdAt = daysFromNow(-ageDays)
  return {
    settings: QUALITY_PRESETS.medium,
    transcribe: true,
    createdAt,
    updatedAt: createdAt,
    expiresAt: daysFromNow(RETENTION_DAYS - ageDays),
    outputSizeBytes: null,
    hasTranscript: false,
    error: null,
    ...overrides,
  }
}

export async function mockListJobs(): Promise<Job[]> {
  await delay(500)
  return [
    mockJob({ id: 'job-1', status: 'queued', fileName: 'standup-recording.mp4' }, 0),
    mockJob(
      {
        id: 'job-2',
        status: 'processing',
        fileName: 'lecture-week-5.mp4',
        settings: QUALITY_PRESETS.high,
      },
      0,
    ),
    mockJob(
      {
        id: 'job-3',
        status: 'ready',
        fileName: 'group-demo-final.mp4',
        outputSizeBytes: 48_300_000,
        hasTranscript: true,
      },
      1,
    ),
    mockJob(
      {
        id: 'job-4',
        status: 'ready',
        fileName: 'screen-recording 2026-09-24.mp4',
        settings: QUALITY_PRESETS.low,
        transcribe: false,
        outputSizeBytes: 12_900_000,
      },
      5,
    ),
    mockJob(
      {
        id: 'job-5',
        status: 'failed',
        fileName: 'interview-raw.mp4',
        settings: QUALITY_PRESETS.high,
        error: "This file couldn't be read as an MP4 video.",
      },
      6,
    ),
  ]
}

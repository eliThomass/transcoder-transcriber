import { useEffect, useState } from 'react'
import { errorMessage } from '../api/client.ts'
import type { DownloadFile, Job, User } from '../api/types.ts'
import { getDownloadLink, listJobs } from '../jobs/jobsApi.ts'
import { formatDate, formatExpiry, formatFileSize } from '../utils/format.ts'
import './LibraryPage.css'

type LibraryPageProps = {
  user: User | null
  onLogIn: () => void
}

function LibraryPage({ user, onLogIn }: LibraryPageProps) {
  return (
    <main className="page library-page">
      <header className="page__header">
        <h1 className="page__title">Your library</h1>
        <p className="page__description">
          Download videos you&rsquo;ve encoded. Files are kept for a limited time,
          then deleted automatically.
        </p>
      </header>

      {user ? (
        // Keyed by user so logging in as someone else starts a fresh load.
        <LibraryList key={user.id} />
      ) : (
        <div className="library-empty">
          <h2 className="library-empty__title">Log in to see your videos</h2>
          <p className="library-empty__text">
            Videos you encode are saved to your account so you can download them
            later.
          </p>
          <button className="button button--primary" type="button" onClick={onLogIn}>
            Log in
          </button>
        </div>
      )}
    </main>
  )
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; jobs: Job[] }

const STATUS_LABELS = {
  queued: 'Queued',
  processing: 'Processing',
  failed: 'Encoding failed',
} as const

function LibraryList() {
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false
    listJobs()
      .then((jobs) => {
        if (!ignore) setState({ status: 'ready', jobs })
      })
      .catch((error: unknown) => {
        if (!ignore) setState({ status: 'error', message: errorMessage(error) })
      })
    return () => {
      ignore = true
    }
  }, [attempt])

  function handleRetry() {
    setState({ status: 'loading' })
    setAttempt((previous) => previous + 1)
  }

  function handleDownload(job: Job, file: DownloadFile) {
    setDownloadError(null)
    getDownloadLink(job.id, file)
      // The presigned URL serves the file as an attachment, so opening it downloads it.
      .then((link) => window.location.assign(link.url))
      .catch((error: unknown) => setDownloadError(errorMessage(error)))
  }

  if (state.status === 'loading') {
    return (
      <p className="library-page__message" role="status">
        Loading your videos…
      </p>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="library-page__message library-page__message--error" role="alert">
        <p>{state.message}</p>
        <button
          className="button button--secondary button--small"
          type="button"
          onClick={handleRetry}
        >
          Try again
        </button>
      </div>
    )
  }

  if (state.jobs.length === 0) {
    return (
      <div className="library-empty">
        <h2 className="library-empty__title">No videos yet</h2>
        <p className="library-empty__text">Videos you encode will show up here.</p>
        <a className="button button--primary" href="#/encode">
          Encode a video
        </a>
      </div>
    )
  }

  return (
    <>
      {downloadError && (
        <p className="library-page__message library-page__message--error" role="alert">
          {downloadError}
        </p>
      )}
      <ul className="library-list">
        {state.jobs.map((job) => (
          <li className={`library-item library-item--${job.status}`} key={job.id}>
            <div className="library-item__thumb" aria-hidden="true" />
            <div className="library-item__info">
              <p className="library-item__name">{job.fileName}</p>
              <p className="library-item__meta">
                <span>{job.settings.resolution}</span>
                {job.outputSizeBytes !== null && (
                  <span>{formatFileSize(job.outputSizeBytes)}</span>
                )}
                <span>Encoded {formatDate(job.createdAt)}</span>
                <span>{formatExpiry(job.expiresAt)}</span>
              </p>
              {job.status === 'failed' && job.error && (
                <p className="library-item__error">{job.error}</p>
              )}
            </div>
            {job.status === 'ready' ? (
              <div className="library-item__actions">
                <button
                  className="button button--secondary button--small"
                  type="button"
                  aria-label={`Download video: ${job.fileName}`}
                  onClick={() => handleDownload(job, 'video')}
                >
                  Download video
                </button>
                {job.hasTranscript && (
                  <button
                    className="button button--secondary button--small"
                    type="button"
                    aria-label={`Download transcript: ${job.fileName}`}
                    onClick={() => handleDownload(job, 'transcript')}
                  >
                    Download transcript
                  </button>
                )}
              </div>
            ) : (
              <p className={`library-item__status library-item__status--${job.status}`}>
                {STATUS_LABELS[job.status]}
              </p>
            )}
          </li>
        ))}
      </ul>
    </>
  )
}

export default LibraryPage

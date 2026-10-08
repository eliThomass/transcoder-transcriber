import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { errorMessage } from '../api/client.ts'
import { logIn, signUp } from '../auth/authApi.ts'
import type { Credentials, User } from '../api/types.ts'
import type { AuthMode } from '../auth/authApi.ts'
import { API_CONNECTED } from '../config/api.ts'
import './AuthDialog.css'

const COPY = {
  logIn: {
    title: 'Log in',
    submit: 'Log in',
    switchPrompt: 'No account yet?',
    switchAction: 'Sign up',
  },
  signUp: {
    title: 'Create an account',
    submit: 'Sign up',
    switchPrompt: 'Already have an account?',
    switchAction: 'Log in',
  },
} as const

const MIN_PASSWORD_LENGTH = 8

type AuthDialogProps = {
  initialMode: AuthMode
  onClose: () => void
  onAuthenticated: (user: User) => void
}

function AuthDialog({ initialMode, onClose, onAuthenticated }: AuthDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [mode, setMode] = useState<AuthMode>(initialMode)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const copy = COPY[mode]

  // showModal() gives focus trapping, Escape to close and a backdrop for free.
  useEffect(() => {
    dialogRef.current?.showModal()
  }, [])

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    // Read from the form instead of keeping the password in React state.
    const data = new FormData(event.currentTarget)
    const credentials: Credentials = {
      email: String(data.get('email') ?? ''),
      password: String(data.get('password') ?? ''),
    }

    setError(null)
    setIsSubmitting(true)
    const request = mode === 'logIn' ? logIn(credentials) : signUp(credentials)
    request.then(onAuthenticated).catch((requestError: unknown) => {
      setError(errorMessage(requestError))
      setIsSubmitting(false)
    })
  }

  function switchMode() {
    setMode(mode === 'logIn' ? 'signUp' : 'logIn')
    setError(null)
  }

  return (
    <dialog
      ref={dialogRef}
      className="auth-dialog"
      aria-labelledby="auth-dialog-title"
      onClose={onClose}
    >
      <form className="auth-dialog__form" onSubmit={handleSubmit}>
        <div className="auth-dialog__header">
          <h2 className="auth-dialog__title" id="auth-dialog-title">
            {copy.title}
          </h2>
          <button
            className="auth-dialog__close"
            type="button"
            aria-label="Close"
            onClick={onClose}
          >
            <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
              <path
                d="M3.5 3.5l9 9m0-9l-9 9"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>

        <div className="field">
          <label className="field__label" htmlFor="auth-email">
            Email
          </label>
          <input
            className="field__input"
            id="auth-email"
            name="email"
            type="email"
            autoComplete="email"
            required
          />
        </div>

        <div className="field">
          <label className="field__label" htmlFor="auth-password">
            Password
          </label>
          <input
            className="field__input"
            id="auth-password"
            name="password"
            type="password"
            autoComplete={mode === 'logIn' ? 'current-password' : 'new-password'}
            minLength={mode === 'signUp' ? MIN_PASSWORD_LENGTH : undefined}
            aria-describedby={mode === 'signUp' ? 'auth-password-hint' : undefined}
            required
          />
          {mode === 'signUp' && (
            <p className="field__hint" id="auth-password-hint">
              At least {MIN_PASSWORD_LENGTH} characters.
            </p>
          )}
        </div>

        {error && (
          <p className="field__error" role="alert">
            {error}
          </p>
        )}

        <button
          className="button button--primary auth-dialog__submit"
          type="submit"
          disabled={isSubmitting}
        >
          {copy.submit}
        </button>

        <p className="auth-dialog__switch">
          {copy.switchPrompt}{' '}
          <button className="auth-dialog__switch-button" type="button" onClick={switchMode}>
            {copy.switchAction}
          </button>
        </p>

        {import.meta.env.DEV && !API_CONNECTED.auth && (
          <p className="auth-dialog__dev-note">
            Dev mode: accounts aren&rsquo;t connected, so any email and password logs
            in with mock data.
          </p>
        )}
      </form>
    </dialog>
  )
}

export default AuthDialog

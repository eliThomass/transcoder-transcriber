import type { User } from '../api/types.ts'
import { TABS } from '../config/navigation.ts'
import type { TabId } from '../config/navigation.ts'
import './TopBar.css'

type TopBarProps = {
  activeTab: TabId
  user: User | null
  onLogIn: () => void
  onSignUp: () => void
  onLogOut: () => void
}

function TopBar({ activeTab, user, onLogIn, onSignUp, onLogOut }: TopBarProps) {
  return (
    <header className="top-bar">
      <div className="top-bar__inner">
        <a className="top-bar__brand" href="#/encode">
          Transcode &amp; Transcribe
        </a>

        <nav className="top-bar__nav" aria-label="Main">
          {TABS.map((tab) => (
            <a
              key={tab.id}
              className="top-bar__tab"
              href={tab.href}
              aria-current={tab.id === activeTab ? 'page' : undefined}
            >
              {tab.label}
            </a>
          ))}
        </nav>

        <div className="top-bar__account">
          {user ? (
            <>
              <span className="top-bar__user" title={user.email}>
                {user.email}
              </span>
              <button className="top-bar__button" type="button" onClick={onLogOut}>
                Log out
              </button>
            </>
          ) : (
            <>
              <button className="top-bar__button" type="button" onClick={onLogIn}>
                Log in
              </button>
              <button
                className="top-bar__button top-bar__button--primary"
                type="button"
                onClick={onSignUp}
              >
                Sign up
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

export default TopBar

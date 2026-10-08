import { useEffect, useState } from 'react'
import { getCurrentUser, logOut } from './auth/authApi.ts'
import type { User } from './api/types.ts'
import type { AuthMode } from './auth/authApi.ts'
import AuthDialog from './components/AuthDialog.tsx'
import TopBar from './components/TopBar.tsx'
import { tabFromHash } from './config/navigation.ts'
import type { TabId } from './config/navigation.ts'
import LibraryPage from './pages/LibraryPage.tsx'
import UploadPage from './pages/UploadPage.tsx'

function App() {
  const [activeTab, setActiveTab] = useState<TabId>(() =>
    tabFromHash(window.location.hash),
  )
  const [user, setUser] = useState<User | null>(null)
  // Which auth dialog is open, or null when it's closed.
  const [authMode, setAuthMode] = useState<AuthMode | null>(null)

  useEffect(() => {
    function handleHashChange() {
      setActiveTab(tabFromHash(window.location.hash))
    }
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  // Restore an existing session on page load (the API reads its session cookie).
  useEffect(() => {
    let ignore = false
    getCurrentUser()
      .then((currentUser) => {
        if (!ignore) setUser(currentUser)
      })
      .catch(() => {
        // Treat a failed session check as logged out.
      })
    return () => {
      ignore = true
    }
  }, [])

  function handleAuthenticated(authenticatedUser: User) {
    setUser(authenticatedUser)
    setAuthMode(null)
  }

  function handleLogOut() {
    logOut()
      .catch(() => {
        // Clear the local session even if the request fails.
      })
      .finally(() => setUser(null))
  }

  return (
    <>
      <TopBar
        activeTab={activeTab}
        user={user}
        onLogIn={() => setAuthMode('logIn')}
        onSignUp={() => setAuthMode('signUp')}
        onLogOut={handleLogOut}
      />

      {activeTab === 'encode' ? (
        <UploadPage />
      ) : (
        <LibraryPage user={user} onLogIn={() => setAuthMode('logIn')} />
      )}

      {authMode && (
        <AuthDialog
          initialMode={authMode}
          onClose={() => setAuthMode(null)}
          onAuthenticated={handleAuthenticated}
        />
      )}
    </>
  )
}

export default App

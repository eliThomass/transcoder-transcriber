import { useEffect, useState } from 'react'
import { getCurrentUser, logIn, logOut, signUp } from './auth/authApi.ts'
import type { User } from './api/types.ts'
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

  // On success the page navigates to Cognito's logout; on failure just show the app as logged out.
  function handleLogOut() {
    logOut().catch(() => setUser(null))
  }

  return (
    <>
      <TopBar
        activeTab={activeTab}
        user={user}
        onLogIn={logIn}
        onSignUp={signUp}
        onLogOut={handleLogOut}
      />

      {activeTab === 'encode' ? <UploadPage /> : <LibraryPage user={user} onLogIn={logIn} />}
    </>
  )
}

export default App

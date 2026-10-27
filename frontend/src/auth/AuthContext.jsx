import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { refreshSession, setAccessToken, setOnAuthLost } from '../api/client'
import { authApi } from '../api/endpoints'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false) // false until we know whether a session exists

  useEffect(() => {
    // Called by the API client when a refresh fails mid-session (expired or deactivated)
    setOnAuthLost(() => {
      setAccessToken(null)
      setUser(null)
    })
    // On page load the in-memory token is gone; the refresh cookie may still be valid
    refreshSession().then((session) => {
      if (session) setUser(session.user)
      setReady(true)
    })
  }, [])

  const login = useCallback(async (email, password) => {
    const data = await authApi.login(email, password)
    setAccessToken(data.access_token)
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      // Clear local state even if the server can't be reached
    }
    setAccessToken(null)
    setUser(null)
  }, [])

  const value = useMemo(() => ({ user, ready, login, logout }), [user, ready, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}

import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'

// Wrap routes that need a logged-in user, optionally limited to some roles.
// The backend enforces the same rules; this only keeps users off pages they can't use.
export function ProtectedRoute({ roles }) {
  const { user, ready } = useAuth()
  const location = useLocation()

  if (!ready) return <div className="page-loading">Loading…</div>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (roles && !roles.includes(user.role)) {
    return (
      <div className="card empty-state">
        <h2>Not available</h2>
        <p>Your role doesn't have access to this page.</p>
      </div>
    )
  }
  return <Outlet />
}

// Login/register pages: send already-logged-in users to the dashboard
export function GuestOnly() {
  const { user, ready } = useAuth()
  if (!ready) return <div className="page-loading">Loading…</div>
  if (user) return <Navigate to="/" replace />
  return <Outlet />
}

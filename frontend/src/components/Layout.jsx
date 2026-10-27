import { useRef } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { ROLE_LABELS } from '../auth/roles'
import { LnmiitLogo } from './Brand'
import { useActiveIndicator } from './effects'
import { NotificationBell } from './NotificationBell'
import { ThemeToggle } from './ThemeToggle'

// NFR-009: the same navigation on every page; links depend on the user's role.
export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const navRef = useRef(null)
  const indicator = useActiveIndicator(navRef, location.pathname)

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  const initials = user.full_name
    .replace(/^(dr|prof)\.?\s+/i, '')
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <div className="app-shell">
      <div className="app-backdrop" aria-hidden="true" />
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="brand">
            <LnmiitLogo size={36} />
            <span className="brand-text">
              <span className="brand-title">Faculty Collaboration Network</span>
              <span className="brand-sub">LNMIIT Jaipur</span>
            </span>
          </NavLink>

          <nav className="nav" ref={navRef}>
            {indicator && (
              <span className="nav-indicator" style={{ transform: `translateX(${indicator.left}px)`, width: indicator.width }} />
            )}
            <NavLink to="/" end>Dashboard</NavLink>
            {user.role === 'faculty' && <NavLink to="/profile">My profile</NavLink>}
            <NavLink to="/search">Search</NavLink>
            {user.role === 'faculty' && <NavLink to="/collaborations">Collaborations</NavLink>}
            {user.role === 'admin' && <NavLink to="/admin/users">Users</NavLink>}
            {user.role === 'admin' && <NavLink to="/admin/approvals">Approvals</NavLink>}
            {(user.role === 'admin' || user.role === 'research_admin') && <NavLink to="/reports" end>Reports</NavLink>}
            {user.role === 'dept_mgmt' && <NavLink to="/reports/department">My department</NavLink>}
            {user.role === 'research_admin' && <NavLink to="/reports/department">Departments report</NavLink>}
            {user.role === 'admin' && <NavLink to="/departments">Departments</NavLink>}
          </nav>

          <div className="user-menu">
            <div className="user-meta">
              <span className="user-name">{user.full_name}</span>
              <span className="role-chip">{ROLE_LABELS[user.role] ?? user.role}</span>
            </div>
            {user.role === 'faculty' && <NotificationBell />}
            <ThemeToggle />
            <NavLink to="/account" className="avatar" title="Account settings" aria-label="Account settings">{initials}</NavLink>
            <button className="btn btn-ghost btn-sm" onClick={handleLogout}>Log out</button>
          </div>
        </div>
      </header>

      {/* key on the path so each page plays its entrance animation */}
      <main className="content page-enter" key={location.pathname}>
        <Outlet />
      </main>
    </div>
  )
}

// Login / register: animated aurora background with a glass card
export function AuthShell({ title, subtitle, children }) {
  return (
    <div className="auth-shell">
      <ThemeToggle className="auth-theme-toggle" />
      <div className="aurora" aria-hidden="true">
        <span className="blob blob-1" />
        <span className="blob blob-2" />
        <span className="blob blob-3" />
        <span className="grid-overlay" />
      </div>

      <div className="auth-brand">
        <div className="logo-halo">
          <LnmiitLogo size={76} />
        </div>
        <h1>Faculty Collaboration Network</h1>
        <p>The LNM Institute of Information Technology, Jaipur</p>
      </div>

      <div className="card glass auth-card">
        <h2>{title}</h2>
        {subtitle && <p className="muted">{subtitle}</p>}
        {children}
      </div>
    </div>
  )
}

import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { GuestOnly, ProtectedRoute } from './auth/ProtectedRoute'
import { Layout } from './components/Layout'
import Account from './pages/Account'
import AdminUsers from './pages/AdminUsers'
import Approvals from './pages/Approvals'
import AuditLog from './pages/AuditLog'
import Collaborations from './pages/Collaborations'
import Dashboard from './pages/Dashboard'
import DepartmentReport from './pages/DepartmentReport'
import Departments from './pages/Departments'
import ForgotPassword from './pages/ForgotPassword'
import Login from './pages/Login'
import MyProfile from './pages/MyProfile'
import Notifications from './pages/Notifications'
import ProfileView from './pages/ProfileView'
import Register from './pages/Register'
import Reports from './pages/Reports'
import ResetPassword from './pages/ResetPassword'
import Search from './pages/Search'

function NotFound() {
  return (
    <div className="card empty-state">
      <h2>Page not found</h2>
      <p className="muted">The page you're looking for doesn't exist.</p>
      <Link to="/" className="btn btn-primary">Go to dashboard</Link>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<GuestOnly />}>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
          </Route>
          {/* Works whether or not you're signed in: the link comes from an email */}
          <Route path="/reset-password" element={<ResetPassword />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="/search" element={<Search />} />
              <Route path="/notifications" element={<Notifications />} />
              <Route path="/account" element={<Account />} />
              <Route path="/profiles/:userId" element={<ProfileView />} />
              <Route element={<ProtectedRoute roles={['faculty']} />}>
                <Route path="/profile" element={<MyProfile />} />
                <Route path="/collaborations" element={<Collaborations />} />
              </Route>
              <Route element={<ProtectedRoute roles={['admin']} />}>
                {/* Faculty choose their department on the profile form; only admins manage the list */}
                <Route path="/departments" element={<Departments />} />
                <Route path="/admin/approvals" element={<Approvals />} />
                <Route path="/admin/users" element={<AdminUsers />} />
                <Route path="/admin/audit" element={<AuditLog />} />
              </Route>
              <Route element={<ProtectedRoute roles={['admin', 'research_admin']} />}>
                <Route path="/reports" element={<Reports />} />
              </Route>
              <Route element={<ProtectedRoute roles={['admin', 'research_admin', 'dept_mgmt']} />}>
                <Route path="/reports/department" element={<DepartmentReport />} />
              </Route>
              <Route path="*" element={<NotFound />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

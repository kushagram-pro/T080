import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { AuthShell } from '../components/Layout'
import { Alert, Field } from '../components/ui'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [status, setStatus] = useState(null) // 403: pending / rejected / deactivated
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setStatus(null)
    setSubmitting(true)
    try {
      await login(email, password)
      navigate(location.state?.from ?? '/', { replace: true })
    } catch (err) {
      if (err.status === 403) setStatus(err.message)
      else setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const wasRejected = status?.includes('not approved')

  return (
    <AuthShell title="Log in" subtitle="Use your institutional email and password.">
      <form onSubmit={handleSubmit} className="form" noValidate>
        <Alert>{error}</Alert>
        {status && (
          <Alert kind="warning">
            {status}
            {wasRejected && (
              <>
                {' '}You can <Link to="/register">register again</Link> with corrected details.
              </>
            )}
          </Alert>
        )}
        <Field label="Email">
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
          />
        </Field>
        <Field label="Password" hint={<Link to="/forgot-password">Forgot password?</Link>}>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
        <button className="btn btn-primary btn-block" disabled={submitting || !email || !password}>
          {submitting ? 'Logging in…' : 'Log in'}
        </button>
      </form>
      <p className="auth-switch">
        New to the portal? <Link to="/register">Create an account</Link>
      </p>
    </AuthShell>
  )
}

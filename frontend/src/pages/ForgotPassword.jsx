import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../api/endpoints'
import { AuthShell } from '../components/Layout'
import { Alert, Field } from '../components/ui'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(null)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function submit(e) {
    e.preventDefault()
    if (!email.trim()) {
      setError('Enter the email you registered with')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      // Same reply whether or not the account exists, so this can't be used to probe emails
      const res = await authApi.forgotPassword(email)
      setSent(res.message)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (sent) {
    return (
      <AuthShell title="Check your email">
        <div className="success-panel">
          <div className="success-icon" aria-hidden="true">✓</div>
          <p>{sent}</p>
          <p className="muted small">Didn't get it? Check spam, or try again in a minute.</p>
        </div>
        <Link to="/login" className="btn btn-primary btn-block">Back to log in</Link>
      </AuthShell>
    )
  }

  return (
    <AuthShell title="Reset your password" subtitle="We'll email you a link to choose a new password.">
      <form className="form" onSubmit={submit} noValidate>
        <Alert>{error}</Alert>
        <Field label="Institutional email">
          <input type="email" autoComplete="username" value={email} autoFocus
            onChange={(e) => { setEmail(e.target.value); setError(null) }} />
        </Field>
        <button className="btn btn-primary btn-block" disabled={submitting}>
          {submitting ? 'Sending…' : 'Send reset link'}
        </button>
      </form>
      <p className="auth-switch">
        Remembered it? <Link to="/login">Back to log in</Link>
      </p>
    </AuthShell>
  )
}

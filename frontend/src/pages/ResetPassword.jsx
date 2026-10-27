import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { AuthShell } from '../components/Layout'
import { Alert, Field } from '../components/ui'

// The emailed link is /reset-password#token=… (fragment, so the token never reaches server logs).
// Read it once, then strip it from the address bar so it doesn't linger in history.
function takeTokenFromUrl() {
  const token = new URLSearchParams(window.location.hash.slice(1)).get('token')
  if (token) window.history.replaceState(null, '', window.location.pathname)
  return token
}

export default function ResetPassword() {
  const { user, logout } = useAuth()
  const [token] = useState(takeTokenFromUrl)
  const [form, setForm] = useState({ next: '', confirm: '' })
  const [errors, setErrors] = useState({})
  const [error, setError] = useState(null)
  const [done, setDone] = useState(null)
  const [saving, setSaving] = useState(false)

  // The reset ends every session server-side; drop any local one too
  useEffect(() => {
    if (done && user) logout()
  }, [done, user, logout])

  const set = (name) => (e) => {
    setForm((f) => ({ ...f, [name]: e.target.value }))
    setErrors((x) => ({ ...x, [name]: undefined }))
  }

  async function submit(e) {
    e.preventDefault()
    const errs = {}
    if (form.next.length < 8 || !/[a-zA-Z]/.test(form.next) || !/\d/.test(form.next))
      errs.next = 'At least 8 characters, with a letter and a number'
    if (form.confirm !== form.next) errs.confirm = "Passwords don't match"
    setErrors(errs)
    if (Object.keys(errs).length) return
    setSaving(true)
    setError(null)
    try {
      const res = await authApi.resetPassword(token, form.next)
      setDone(res.message)
    } catch (err) {
      if (err.fieldErrors?.new_password) setErrors({ next: err.fieldErrors.new_password })
      else setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (!token) {
    return (
      <AuthShell title="Link not valid">
        <Alert>This reset link is incomplete. Open it straight from the email, or request a new one.</Alert>
        <Link to="/forgot-password" className="btn btn-primary btn-block">Request a new link</Link>
      </AuthShell>
    )
  }

  if (done) {
    return (
      <AuthShell title="Password updated">
        <div className="success-panel">
          <div className="success-icon" aria-hidden="true">✓</div>
          <p>{done}</p>
          <p className="muted small">For your security, you've been signed out everywhere.</p>
        </div>
        <Link to="/login" className="btn btn-primary btn-block">Log in</Link>
      </AuthShell>
    )
  }

  const expired = error && /expired|invalid|already been used/i.test(error)

  return (
    <AuthShell title="Choose a new password">
      <form className="form" onSubmit={submit} noValidate>
        {error && (
          <Alert>
            {error}
            {expired && <> <Link to="/forgot-password">Request a new link</Link>.</>}
          </Alert>
        )}
        <Field label="New password" error={errors.next} hint="At least 8 characters, with a letter and a number">
          <input type="password" autoComplete="new-password" value={form.next} onChange={set('next')} autoFocus />
        </Field>
        <Field label="Confirm new password" error={errors.confirm}>
          <input type="password" autoComplete="new-password" value={form.confirm} onChange={set('confirm')} />
        </Field>
        <button className="btn btn-primary btn-block" disabled={saving}>{saving ? 'Saving…' : 'Set new password'}</button>
      </form>
    </AuthShell>
  )
}

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../api/endpoints'
import { AuthShell } from '../components/Layout'
import { Alert, Field } from '../components/ui'

const EMAIL_DOMAIN = import.meta.env.VITE_EMAIL_DOMAIN ?? 'lnmiit.ac.in'

// Mirrors the backend rules so users get instant feedback; the backend still validates.
function validate({ full_name, email, password, confirm }) {
  const errors = {}
  if (!full_name.trim()) errors.full_name = 'Full name is required'
  if (!email.trim()) errors.email = 'Email is required'
  else if (!email.trim().toLowerCase().endsWith(`@${EMAIL_DOMAIN}`))
    errors.email = `Please use your @${EMAIL_DOMAIN} email address`
  if (password.length < 8) errors.password = 'At least 8 characters'
  else if (!/[a-zA-Z]/.test(password) || !/\d/.test(password))
    errors.password = 'Must contain at least one letter and one number'
  else if (new TextEncoder().encode(password).length > 72) errors.password = 'At most 72 characters'
  if (confirm !== password) errors.confirm = "Passwords don't match"
  return errors
}

export default function Register() {
  const [form, setForm] = useState({ full_name: '', email: '', password: '', confirm: '' })
  const [touched, setTouched] = useState({})
  const [serverErrors, setServerErrors] = useState({})
  const [error, setError] = useState(null)
  const [done, setDone] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const errors = { ...validate(form), ...serverErrors }
  const show = (name) => (touched[name] ? errors[name] : undefined)

  function update(name) {
    return (e) => {
      setForm((f) => ({ ...f, [name]: e.target.value }))
      setServerErrors((s) => ({ ...s, [name]: undefined }))
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setTouched({ full_name: true, email: true, password: true, confirm: true })
    if (Object.keys(validate(form)).length) return
    setError(null)
    setSubmitting(true)
    try {
      const res = await authApi.register({
        full_name: form.full_name,
        email: form.email,
        password: form.password,
      })
      setDone(res.message)
    } catch (err) {
      setServerErrors(err.fieldErrors ?? {})
      if (!Object.keys(err.fieldErrors ?? {}).length) setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (done) {
    return (
      <AuthShell title="Registration received">
        <div className="success-panel">
          <div className="success-icon" aria-hidden="true">✓</div>
          <p>{done}</p>
          <p className="muted">An administrator reviews every new account before it can log in.</p>
        </div>
        <Link to="/login" className="btn btn-primary btn-block">Back to log in</Link>
      </AuthShell>
    )
  }

  return (
    <AuthShell title="Create an account" subtitle="For LNMIIT faculty. An administrator will approve your account.">
      <form onSubmit={handleSubmit} className="form" noValidate>
        <Alert>{error}</Alert>
        <Field label="Full name" error={show('full_name')}>
          <input
            value={form.full_name}
            onChange={update('full_name')}
            onBlur={() => setTouched((t) => ({ ...t, full_name: true }))}
            autoComplete="name"
            maxLength={150}
            autoFocus
          />
        </Field>
        <Field label="Institutional email" error={show('email')} hint={`Must end in @${EMAIL_DOMAIN}`}>
          <input
            type="email"
            value={form.email}
            onChange={update('email')}
            onBlur={() => setTouched((t) => ({ ...t, email: true }))}
            autoComplete="email"
            placeholder={`name@${EMAIL_DOMAIN}`}
          />
        </Field>
        <Field label="Password" error={show('password')} hint="At least 8 characters, with a letter and a number">
          <input
            type="password"
            value={form.password}
            onChange={update('password')}
            onBlur={() => setTouched((t) => ({ ...t, password: true }))}
            autoComplete="new-password"
          />
        </Field>
        <Field label="Confirm password" error={show('confirm')}>
          <input
            type="password"
            value={form.confirm}
            onChange={update('confirm')}
            onBlur={() => setTouched((t) => ({ ...t, confirm: true }))}
            autoComplete="new-password"
          />
        </Field>
        <button className="btn btn-primary btn-block" disabled={submitting}>
          {submitting ? 'Submitting…' : 'Register'}
        </button>
      </form>
      <p className="auth-switch">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </AuthShell>
  )
}

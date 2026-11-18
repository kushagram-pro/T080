import { useState } from 'react'
import { accountApi } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { ROLE_LABELS } from '../auth/roles'
import { Alert, Field } from '../components/ui'

function DigestSetting() {
  const { user, updateUser } = useAuth()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  async function toggle() {
    setSaving(true)
    setError(null)
    try {
      updateUser(await accountApi.setEmailDigest(!user.email_digest))
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="card rise visibility-card">
      <div>
        <h2 className="card-title">Weekly email summary</h2>
        <p className="muted small">
          Once a week: requests waiting for you, unread messages and new colleagues who share your interests.
          Nothing is sent in a week with nothing new.
        </p>
        <Alert>{error}</Alert>
      </div>
      <label className="switch">
        <input type="checkbox" role="switch" checked={user.email_digest} disabled={saving} onChange={toggle} />
        <span>{user.email_digest ? 'On' : 'Off'}</span>
      </label>
    </section>
  )
}

export default function Account() {
  const { user } = useAuth()
  const [form, setForm] = useState({ current: '', next: '', confirm: '' })
  const [errors, setErrors] = useState({})
  const [error, setError] = useState(null)
  const [done, setDone] = useState(null)
  const [saving, setSaving] = useState(false)

  const set = (name) => (e) => {
    setForm((f) => ({ ...f, [name]: e.target.value }))
    setErrors((x) => ({ ...x, [name]: undefined }))
    setDone(null)
  }

  async function submit(e) {
    e.preventDefault()
    const errs = {}
    if (!form.current) errs.current = 'Enter your current password'
    if (form.next.length < 8 || !/[a-zA-Z]/.test(form.next) || !/\d/.test(form.next))
      errs.next = 'At least 8 characters, with a letter and a number'
    if (form.confirm !== form.next) errs.confirm = "Passwords don't match"
    setErrors(errs)
    if (Object.keys(errs).length) return
    setSaving(true)
    setError(null)
    try {
      const res = await accountApi.changePassword(form.current, form.next)
      setForm({ current: '', next: '', confirm: '' })
      setDone(res.message)
    } catch (err) {
      const fe = err.fieldErrors ?? {}
      setErrors({ current: fe.current_password, next: fe.new_password })
      if (!fe.current_password && !fe.new_password) setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="stack-lg narrow">
      <section className="page-header">
        <div>
          <h1>Account</h1>
          <p className="muted">{user.full_name} · {user.email} · {ROLE_LABELS[user.role]}</p>
        </div>
      </section>

      <section className="card rise">
        <h2 className="card-title">Change password</h2>
        <form className="form" onSubmit={submit} noValidate>
          {done && <Alert kind="success">{done}</Alert>}
          <Alert>{error}</Alert>
          <Field label="Current password" error={errors.current}>
            <input type="password" autoComplete="current-password" value={form.current} onChange={set('current')} />
          </Field>
          <Field label="New password" error={errors.next} hint="At least 8 characters, with a letter and a number">
            <input type="password" autoComplete="new-password" value={form.next} onChange={set('next')} />
          </Field>
          <Field label="Confirm new password" error={errors.confirm}>
            <input type="password" autoComplete="new-password" value={form.confirm} onChange={set('confirm')} />
          </Field>
          <div className="form-actions">
            <button className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Change password'}</button>
          </div>
        </form>
      </section>

      {user.role === 'faculty' && <DigestSetting />}
    </div>
  )
}

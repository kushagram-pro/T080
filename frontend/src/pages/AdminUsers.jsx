import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { adminApi, departmentsApi } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { ROLE_LABELS } from '../auth/roles'
import { Alert, Field, Modal, Spinner } from '../components/ui'
import { formatDate } from '../utils/format'

const PAGE_SIZE = 25
const STATUS_LABEL = { active: 'Active', inactive: 'Inactive', pending: 'Pending approval' }
const EMAIL_DOMAIN = import.meta.env.VITE_EMAIL_DOMAIN ?? 'lnmiit.ac.in'

// FR-038 (manage accounts), FR-005 (assign roles), FR-007 (deactivate)
export default function AdminUsers() {
  const { user: me } = useAuth()
  const [params] = useSearchParams()
  // Links like /admin/users?role=faculty pre-set the filters
  const [filters, setFilters] = useState({ q: '', role: params.get('role') ?? '', status: params.get('status') ?? '' })
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [departments, setDepartments] = useState([])
  const [editing, setEditing] = useState(null) // null | 'new' | user row
  const [confirm, setConfirm] = useState(null) // { user, action: 'activate'|'deactivate' }
  const [busy, setBusy] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    departmentsApi.list().then(setDepartments).catch(() => {})
  }, [])

  // Debounced fetch whenever filters / page change
  useEffect(() => {
    let cancelled = false
    const t = setTimeout(() => {
      adminApi
        .users({ ...filters, page, page_size: PAGE_SIZE })
        .then((d) => !cancelled && setData(d))
        .catch((err) => !cancelled && setError(err.message))
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [filters, page, reloadKey])

  const setFilter = (name) => (e) => {
    setFilters((f) => ({ ...f, [name]: e.target.value }))
    setPage(1)
  }

  async function doConfirm() {
    setBusy(true)
    setError(null)
    try {
      const { user, action } = confirm
      const updated = action === 'deactivate' ? await adminApi.deactivate(user.id) : await adminApi.activate(user.id)
      setData((d) => ({ ...d, results: d.results.map((u) => (u.id === updated.id ? updated : u)) }))
      setNotice(`${updated.full_name} is now ${updated.status === 'active' ? 'active' : 'deactivated'}.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
      setConfirm(null)
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <div className="stack-lg">
      <section className="page-header">
        <div>
          <h1>Users</h1>
          <p className="muted">Create accounts, assign roles and deactivate access. Every change is recorded in the audit log.</p>
        </div>
        <div className="row-actions">
          <Link to="/admin/audit" className="btn btn-ghost">Audit log</Link>
          <button className="btn btn-primary" onClick={() => setEditing('new')}>+ Add user</button>
        </div>
      </section>

      <div className="card filter-bar rise">
        <div className="search-input">
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
          <input value={filters.q} onChange={setFilter('q')} placeholder="Search name or email" aria-label="Search users" />
        </div>
        <select value={filters.role} onChange={setFilter('role')} aria-label="Role">
          <option value="">All roles</option>
          {Object.entries(ROLE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <select value={filters.status} onChange={setFilter('status')} aria-label="Status">
          <option value="">All statuses</option>
          {Object.entries(STATUS_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      {notice && <Alert kind="success">{notice}</Alert>}
      {error && <Alert>{error}</Alert>}
      {data === null && !error && <Spinner />}

      {data && data.results.length === 0 && (
        <div className="card empty-state">
          <h2>No users match</h2>
          <p className="muted">Try a different search or filter.</p>
        </div>
      )}

      {data && data.results.length > 0 && (
        <>
          <p className="result-count muted">{data.total} {data.total === 1 ? 'user' : 'users'}</p>
          <div className="card table-card">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Role</th>
                  <th>Department</th>
                  <th>Status</th>
                  <th>Joined</th>
                  <th className="col-actions"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((u, i) => (
                  <tr key={u.id} className="rise" style={{ '--i': Math.min(i, 12) }}>
                    <td data-label="Name">
                      <div className="strong">
                        {u.has_profile ? <Link to={`/profiles/${u.id}`}>{u.full_name}</Link> : u.full_name}
                        {u.id === me.id && <span className="badge badge-muted">You</span>}
                      </div>
                      <div className="muted small">{u.email}</div>
                    </td>
                    <td data-label="Role">{ROLE_LABELS[u.role]}</td>
                    <td data-label="Department">{u.department_name ?? <span className="muted">—</span>}</td>
                    <td data-label="Status">
                      <span className={`status-pill account-${u.status}`}>{STATUS_LABEL[u.status]}</span>
                    </td>
                    <td data-label="Joined" className="muted small">{formatDate(u.created_at).split(',')[0]}</td>
                    <td className="col-actions">
                      <div className="row-actions">
                        {u.status === 'pending' ? (
                          <Link to="/admin/approvals" className="btn btn-ghost btn-sm">Review</Link>
                        ) : (
                          <>
                            <button className="btn btn-ghost btn-sm" onClick={() => setEditing(u)}>Edit</button>
                            {u.id !== me.id && (
                              u.status === 'active' ? (
                                <button className="btn btn-danger-ghost btn-sm" onClick={() => setConfirm({ user: u, action: 'deactivate' })}>
                                  Deactivate
                                </button>
                              ) : (
                                <button className="btn btn-ghost btn-sm" onClick={() => setConfirm({ user: u, action: 'activate' })}>
                                  Activate
                                </button>
                              )
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <nav className="pager" aria-label="Pages">
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Previous</button>
              <span className="muted small">Page {page} of {totalPages}</span>
              <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next →</button>
            </nav>
          )}
        </>
      )}

      {editing && (
        <UserModal
          user={editing === 'new' ? null : editing}
          isSelf={editing !== 'new' && editing.id === me.id}
          departments={departments}
          onClose={() => setEditing(null)}
          onSaved={(saved, created) => {
            setEditing(null)
            setNotice(created ? `Created ${saved.full_name}'s account. Share the initial password with them.` : `Saved ${saved.full_name}.`)
            setReloadKey((k) => k + 1)
          }}
        />
      )}

      <Modal
        open={confirm !== null}
        title={confirm?.action === 'deactivate' ? `Deactivate ${confirm?.user.full_name}?` : `Activate ${confirm?.user.full_name}?`}
        onClose={() => setConfirm(null)}
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setConfirm(null)}>Cancel</button>
            <button className={confirm?.action === 'deactivate' ? 'btn btn-danger' : 'btn btn-primary'} disabled={busy} onClick={doConfirm}>
              {confirm?.action === 'deactivate' ? 'Deactivate' : 'Activate'}
            </button>
          </>
        }
      >
        <p className="muted">
          {confirm?.action === 'deactivate'
            ? 'They will be signed out on their next action, can’t log in, and disappear from search and suggestions.'
            : 'They will be able to log in again and appear in search.'}
        </p>
      </Modal>
    </div>
  )
}

function UserModal({ user, isSelf, departments, onClose, onSaved }) {
  const creating = user === null
  const [form, setForm] = useState({
    email: '',
    full_name: user?.full_name ?? '',
    password: '',
    role: user?.role ?? 'faculty',
    department_id: user?.role === 'dept_mgmt' ? (user.department_id ?? '') : '',
  })
  const [errors, setErrors] = useState({})
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [reset, setReset] = useState({ busy: false, ok: null, error: null })

  async function sendReset() {
    setReset({ busy: true, ok: null, error: null })
    try {
      const res = await adminApi.sendPasswordReset(user.id)
      setReset({ busy: false, ok: res.message, error: null })
    } catch (err) {
      setReset({ busy: false, ok: null, error: err.message })
    }
  }

  const set = (name) => (e) => {
    setForm((f) => ({ ...f, [name]: e.target.value }))
    setErrors((x) => ({ ...x, [name]: undefined }))
  }

  async function submit(e) {
    e.preventDefault()
    const errs = {}
    if (!form.full_name.trim()) errs.full_name = 'Full name is required'
    if (creating) {
      if (!form.email.trim().toLowerCase().endsWith(`@${EMAIL_DOMAIN}`)) errs.email = `Use an @${EMAIL_DOMAIN} address`
      if (form.password.length < 8 || !/[a-zA-Z]/.test(form.password) || !/\d/.test(form.password))
        errs.password = 'At least 8 characters, with a letter and a number'
    }
    if (form.role === 'dept_mgmt' && !form.department_id) errs.department_id = 'Choose the department they manage'
    setErrors(errs)
    if (Object.keys(errs).length) return

    const department_id = form.role === 'dept_mgmt' ? Number(form.department_id) : null
    setSaving(true)
    setError(null)
    try {
      const saved = creating
        ? await adminApi.createUser({ email: form.email, full_name: form.full_name, password: form.password, role: form.role, department_id })
        : await adminApi.updateUser(user.id, { full_name: form.full_name, role: form.role, department_id })
      onSaved(saved, creating)
    } catch (err) {
      setErrors(err.fieldErrors ?? {})
      if (!Object.keys(err.fieldErrors ?? {}).length) setError(err.message)
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      title={creating ? 'Add user' : `Edit ${user.full_name}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" form="user-form" disabled={saving}>{saving ? 'Saving…' : creating ? 'Create account' : 'Save'}</button>
        </>
      }
    >
      <form id="user-form" className="form" onSubmit={submit} noValidate>
        <Alert>{error}</Alert>
        <Field label="Full name" error={errors.full_name}>
          <input value={form.full_name} maxLength={150} onChange={set('full_name')} autoFocus />
        </Field>
        {creating && (
          <>
            <Field label="Institutional email" error={errors.email}>
              <input type="email" value={form.email} onChange={set('email')} placeholder={`name@${EMAIL_DOMAIN}`} />
            </Field>
            <Field label="Initial password" error={errors.password} hint="Share it with them; they can change it under Account.">
              <input type="text" value={form.password} onChange={set('password')} autoComplete="off" />
            </Field>
          </>
        )}
        <Field label="Role" error={errors.role} hint={isSelf ? "You can't change your own role." : 'Each user has exactly one role.'}>
          <select value={form.role} onChange={set('role')} disabled={isSelf}>
            {Object.entries(ROLE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
        {form.role === 'dept_mgmt' && (
          <Field label="Department they manage" error={errors.department_id}>
            <select value={form.department_id} onChange={set('department_id')}>
              <option value="">Select…</option>
              {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
        )}
      </form>

      {!creating && user.status === 'active' && (
        <div className="modal-section">
          <div>
            <strong>Password</strong>
            <p className="muted small">Email {user.email} a single-use link to choose a new password.</p>
          </div>
          {reset.ok && <Alert kind="success">{reset.ok}</Alert>}
          {reset.error && <Alert>{reset.error}</Alert>}
          <button type="button" className="btn btn-ghost btn-sm" disabled={reset.busy || !!reset.ok} onClick={sendReset}>
            {reset.busy ? 'Sending…' : reset.ok ? 'Sent' : 'Send password reset link'}
          </button>
        </div>
      )}
    </Modal>
  )
}

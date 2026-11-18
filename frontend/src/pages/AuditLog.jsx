import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { adminApi } from '../api/endpoints'
import { Alert, Spinner } from '../components/ui'
import { formatDate } from '../utils/format'

const ACTION_LABEL = {
  account_approved: 'Approved registration',
  account_rejected: 'Rejected registration',
  account_created: 'Created account',
  account_activated: 'Activated account',
  account_deactivated: 'Deactivated account',
  role_changed: 'Changed role',
  department_created: 'Added department',
  department_updated: 'Edited department',
  department_deleted: 'Deleted department',
  password_reset_sent: 'Sent password reset',
}

const EMPTY = { action: '', actor_id: '', target: '', date_from: '', date_to: '' }

// NFR-008: significant administrative actions, newest first
export default function AuditLog() {
  const [filters, setFilters] = useState(EMPTY)
  const [target, setTarget] = useState('') // typed text; applied after a short pause
  const [admins, setAdmins] = useState([])
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    adminApi.users({ role: 'admin', page_size: 100 }).then((r) => setAdmins(r.results)).catch(() => {})
  }, [])

  useEffect(() => {
    const t = window.setTimeout(() => {
      setFilters((f) => (f.target === target.trim() ? f : { ...f, target: target.trim() }))
      setPage(1)
    }, 350)
    return () => window.clearTimeout(t)
  }, [target])

  useEffect(() => {
    let cancelled = false
    adminApi
      .auditLogs({ ...filters, page, page_size: 30 })
      .then((d) => {
        if (cancelled) return
        setData(d)
        setError(null)
      })
      .catch((err) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [filters, page])

  const setFilter = (name) => (e) => {
    setFilters((f) => ({ ...f, [name]: e.target.value }))
    setPage(1)
  }
  const filtered = Object.values(filters).some(Boolean) || target

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <div className="stack-lg">
      <section className="page-header">
        <div>
          <h1>Audit log</h1>
          <p className="muted">Who changed what, and when. Entries can't be edited or deleted from the portal.</p>
        </div>
        <Link to="/admin/users" className="btn btn-ghost">← Users</Link>
      </section>

      <div className="card filter-bar audit-filters rise">
        <select value={filters.action} onChange={setFilter('action')} aria-label="Action">
          <option value="">All actions</option>
          {Object.entries(ACTION_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <select value={filters.actor_id} onChange={setFilter('actor_id')} aria-label="Done by">
          <option value="">Any administrator</option>
          {admins.map((a) => <option key={a.id} value={a.id}>{a.full_name}</option>)}
        </select>
        <input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="Account name or email"
          aria-label="Affected account" maxLength={200} />
        <label className="date-field">
          <span>From</span>
          <input type="date" value={filters.date_from} max={filters.date_to || undefined} onChange={setFilter('date_from')} />
        </label>
        <label className="date-field">
          <span>To</span>
          <input type="date" value={filters.date_to} min={filters.date_from || undefined} onChange={setFilter('date_to')} />
        </label>
        {filtered && (
          <button className="btn btn-ghost btn-sm" onClick={() => { setFilters(EMPTY); setTarget(''); setPage(1) }}>
            Clear
          </button>
        )}
      </div>

      {error && <Alert>{error}</Alert>}
      {data === null && !error && <Spinner />}
      {data?.results.length === 0 && (
        <div className="card empty-state">
          <h2>{filtered ? 'No matching entries' : 'Nothing recorded yet'}</h2>
          {filtered && <p className="muted">Try a wider date range or fewer filters.</p>}
        </div>
      )}

      {data?.results.length > 0 && (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>By</th>
                <th>Account</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((e, i) => (
                <tr key={e.id} className="rise" style={{ '--i': Math.min(i, 12) }}>
                  <td data-label="When" className="muted small nowrap">{formatDate(e.created_at)}</td>
                  <td data-label="Action" className="strong">{ACTION_LABEL[e.action] ?? e.action}</td>
                  <td data-label="By">{e.actor_name ?? <span className="muted">—</span>}</td>
                  <td data-label="Account">
                    {e.target_name ? (<>{e.target_name}<div className="muted small">{e.target_email}</div></>) : <span className="muted">—</span>}
                  </td>
                  <td data-label="Details" className="small">{e.details ?? <span className="muted">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <nav className="pager" aria-label="Pages">
          <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Newer</button>
          <span className="muted small">Page {page} of {totalPages}</span>
          <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Older →</button>
        </nav>
      )}
    </div>
  )
}

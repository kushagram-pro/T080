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
}

// NFR-008: significant administrative actions, newest first
export default function AuditLog() {
  const [action, setAction] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    adminApi
      .auditLogs({ action, page, page_size: 30 })
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [action, page])

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

      <div className="card filter-bar filter-bar-single rise">
        <select value={action} onChange={(e) => { setAction(e.target.value); setPage(1) }} aria-label="Action">
          <option value="">All actions</option>
          {Object.entries(ACTION_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      {error && <Alert>{error}</Alert>}
      {data === null && !error && <Spinner />}
      {data?.results.length === 0 && (
        <div className="card empty-state"><h2>Nothing recorded yet</h2></div>
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

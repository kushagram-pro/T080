import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { departmentsApi, reportsApi } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { BarList } from '../components/charts'
import { Alert, Spinner } from '../components/ui'
import { timeAgo } from '../utils/format'

// FR-044: one department's expertise and collaboration activity.
// Department Management always sees their own; Admin / Research Admin pick one.
export default function DepartmentReport() {
  const { user } = useAuth()
  const canChoose = user.role !== 'dept_mgmt'
  const [params, setParams] = useSearchParams()
  const departmentId = params.get('department_id') ?? ''
  const [departments, setDepartments] = useState([])
  const [state, setState] = useState({ key: null, report: null, error: null })

  useEffect(() => {
    if (canChoose) departmentsApi.list().then(setDepartments).catch(() => {})
  }, [canChoose])

  const needsChoice = canChoose && !departmentId
  useEffect(() => {
    if (needsChoice) return
    let cancelled = false
    reportsApi
      .department(canChoose ? departmentId : undefined)
      .then((report) => !cancelled && setState({ key: departmentId, report, error: null }))
      .catch((error) => !cancelled && setState({ key: departmentId, report: null, error }))
    return () => {
      cancelled = true
    }
  }, [canChoose, departmentId, needsChoice])

  const loading = !needsChoice && state.key !== departmentId
  const { report, error } = state

  return (
    <div className="stack-lg">
      <section className="page-header">
        <div>
          <h1>{report && !loading ? report.department : 'Department summary'}</h1>
          <p className="muted">
            {report && !loading ? `${report.institute} · expertise and collaboration activity` : 'Expertise and collaboration activity within one department.'}
          </p>
        </div>
        {canChoose && (
          <select className="select-inline" value={departmentId} aria-label="Department"
            onChange={(e) => setParams(e.target.value ? { department_id: e.target.value } : {})}>
            <option value="">Choose a department…</option>
            {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        )}
      </section>

      {needsChoice && (
        <div className="card empty-state"><h2>Choose a department</h2><p className="muted">Pick one above to see its summary.</p></div>
      )}
      {!needsChoice && loading && <Spinner />}
      {!loading && error && <Alert>{error.message}</Alert>}

      {!loading && report && (
        <>
          <section className="grid-stats">
            {[
              { label: 'Faculty with profiles', value: report.faculty.length, note: `${report.faculty.filter((f) => f.discoverable).length} complete enough to appear in search` },
              { label: 'Collaborations', value: report.collaborations.length, note: 'involving this department' },
              { label: 'Pending requests', value: report.requests.pending, note: `${report.requests.accepted} accepted so far` },
            ].map((t, i) => (
              <div key={t.label} className="card stat-card rise" style={{ '--i': i }}>
                <span className="stat-label">{t.label}</span>
                <span className="stat-value">{t.value}</span>
                <span className="muted small">{t.note}</span>
              </div>
            ))}
          </section>

          <section className="card table-card rise" style={{ '--i': 3 }}>
            <h2 className="card-title table-title">Faculty</h2>
            {report.faculty.length === 0 ? (
              <p className="muted small table-title">No active faculty with a profile in this department yet.</p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Expertise</th>
                    <th className="num">Publications</th>
                    <th className="num">Projects</th>
                    <th className="num">Collaborations</th>
                  </tr>
                </thead>
                <tbody>
                  {report.faculty.map((f) => (
                    <tr key={f.user_id}>
                      <td data-label="Name">
                        <Link to={`/profiles/${f.user_id}`} className="strong">{f.full_name}</Link>
                        <div className="muted small">
                          {f.designation ?? 'No designation'}
                          {!f.discoverable && ' · profile incomplete'}
                        </div>
                      </td>
                      <td data-label="Expertise" className="small">{f.expertise.join(', ') || <span className="muted">—</span>}</td>
                      <td data-label="Publications" className="num">{f.publications}</td>
                      <td data-label="Projects" className="num">{f.projects}</td>
                      <td data-label="Collaborations" className="num">{f.collaborations}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <div className="grid-2">
            <section className="card rise" style={{ '--i': 4 }}>
              <h2 className="card-title">Expertise in this department</h2>
              <BarList items={report.top_expertise} label="Expertise keywords in this department" />
            </section>
            <section className="card rise" style={{ '--i': 5 }}>
              <h2 className="card-title">Research interests</h2>
              <BarList items={report.top_interests} label="Research interests in this department" />
            </section>
          </div>

          <section className="card rise" style={{ '--i': 6 }}>
            <h2 className="card-title">Collaborations</h2>
            {report.collaborations.length === 0 ? (
              <p className="muted small">No collaborations involving this department yet.</p>
            ) : (
              <ul className="partner-list">
                {report.collaborations.map((c, i) => (
                  <li key={i}>
                    <strong>{c.member}</strong>
                    <span className="partner-link" aria-hidden="true">↔</span>
                    <span>
                      {c.partner}
                      <span className="muted small"> · {c.partner_department ?? 'No department'}</span>
                    </span>
                    <span className="muted small partner-since">since {timeAgo(c.since)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  )
}

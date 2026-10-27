import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { reportsApi } from '../api/endpoints'
import { BarList, MonthColumns } from '../components/charts'
import { Alert, Spinner } from '../components/ui'
import { formatDate } from '../utils/format'

// FR-043: collaboration activity across all departments (Research Admin / Admin)
export default function Reports() {
  const [report, setReport] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    reportsApi.activity().then(setReport).catch((err) => setError(err.message))
  }, [])

  if (error) return <Alert>{error}</Alert>
  if (!report) return <Spinner label="Building report…" />

  const r = report.requests
  const tiles = [
    // Counts faculty who have a profile; the admin dashboard's "registered faculty" also counts those without one
    { label: 'Faculty with profiles', value: report.active_faculty, note: `${report.discoverable_profiles} complete enough to appear in search` },
    { label: 'Collaborations', value: report.collaborations, note: `${report.cross_department_collaborations} across departments` },
    { label: 'Pending requests', value: r.pending, note: `${r.accepted + r.declined + r.withdrawn} answered or withdrawn` },
    {
      label: 'Acceptance rate',
      value: report.acceptance_rate === null ? '–' : `${Math.round(report.acceptance_rate * 100)}%`,
      note: `${r.accepted} accepted · ${r.declined} declined`,
    },
  ]

  return (
    <div className="stack-lg">
      <section className="page-header">
        <div>
          <h1>Collaboration activity</h1>
          <p className="muted">Across all departments · generated {formatDate(report.generated_at)}</p>
        </div>
      </section>

      <section className="grid-stats">
        {tiles.map((t, i) => (
          <div key={t.label} className="card stat-card rise" style={{ '--i': i }}>
            <span className="stat-label">{t.label}</span>
            <span className="stat-value">{t.value}</span>
            <span className="muted small">{t.note}</span>
          </div>
        ))}
      </section>

      <section className="card rise" style={{ '--i': 4 }}>
        <h2 className="card-title">New collaborations per month</h2>
        <MonthColumns months={report.collaborations_by_month} label="New collaborations per month" />
      </section>

      <section className="card table-card rise" style={{ '--i': 5 }}>
        <h2 className="card-title table-title">By department</h2>
        {report.by_department.length === 0 ? (
          <p className="muted small table-title">No departments yet.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Department</th>
                <th className="num">Faculty</th>
                <th className="num">Complete profiles</th>
                <th className="num">Collaborations</th>
                <th className="num">Cross-department</th>
                <th className="num">Pending requests</th>
              </tr>
            </thead>
            <tbody>
              {report.by_department.map((d) => (
                <tr key={d.department_id}>
                  <td data-label="Department" className="strong">
                    <Link to={`/reports/department?department_id=${d.department_id}`}>{d.department}</Link>
                  </td>
                  <td data-label="Faculty" className="num">{d.faculty}</td>
                  <td data-label="Complete profiles" className="num">{d.discoverable_profiles}</td>
                  <td data-label="Collaborations" className="num">{d.collaborations}</td>
                  <td data-label="Cross-department" className="num">{d.cross_department}</td>
                  <td data-label="Pending requests" className="num">{d.pending_requests}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <div className="grid-2">
        <section className="card rise" style={{ '--i': 6 }}>
          <h2 className="card-title">Most common expertise</h2>
          <BarList items={report.top_expertise} label="Most common expertise keywords" />
        </section>
        <section className="card rise" style={{ '--i': 7 }}>
          <h2 className="card-title">Most common research interests</h2>
          <BarList items={report.top_interests} label="Most common research interests" />
        </section>
      </div>
    </div>
  )
}

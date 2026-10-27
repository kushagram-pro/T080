import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { departmentsApi, profilesApi, searchApi } from '../api/endpoints'
import { Alert, Spinner } from '../components/ui'

const PAGE_SIZE = 12

// The URL is the source of truth (?q=…&department_id=…&designation=…&page=…),
// so results survive a reload and the back button returns to them (FR-022).
export default function Search() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const departmentId = params.get('department_id') ?? ''
  const designation = params.get('designation') ?? ''
  const page = Number(params.get('page') ?? 1)
  const hasQuery = Boolean(q.trim() || departmentId || designation)

  const [departments, setDepartments] = useState([])
  const [designations, setDesignations] = useState([])
  const [prompt, setPrompt] = useState(null)
  // Each result remembers which search it answers; "loading" = the URL asks for a different one
  const [state, setState] = useState({ key: null, data: null, error: null })
  const searchKey = `${q}|${departmentId}|${designation}|${page}`

  useEffect(() => {
    departmentsApi.list().then(setDepartments).catch(() => {})
    profilesApi.designations().then(setDesignations).catch(() => {})
  }, [])

  useEffect(() => {
    if (!hasQuery) return
    let cancelled = false
    searchApi
      .search({ q, department_id: departmentId, designation, page, page_size: PAGE_SIZE })
      .then((data) => !cancelled && setState({ key: searchKey, data, error: null }))
      .catch((error) => !cancelled && setState({ key: searchKey, data: null, error }))
    return () => {
      cancelled = true
    }
  }, [hasQuery, q, departmentId, designation, page, searchKey])

  function search(form) {
    setPrompt(null)
    const next = {}
    if (form.q.trim()) next.q = form.q.trim()
    if (form.department_id) next.department_id = form.department_id
    if (form.designation) next.designation = form.designation
    setParams(next)
  }

  function goToPage(p) {
    const next = new URLSearchParams(params)
    next.set('page', p)
    setParams(next)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const { data, error } = state
  const loading = hasQuery && state.key !== searchKey
  const filtered = Boolean(departmentId || designation)
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <div className="stack-lg">
      <section className="page-header">
        <div>
          <h1>Find collaborators</h1>
          <p className="muted">Search faculty by expertise and research interests. Separate keywords with commas.</p>
        </div>
      </section>

      <SearchForm
        key={`${q}|${departmentId}|${designation}`}
        initial={{ q, department_id: departmentId, designation }}
        departments={departments}
        designations={designations}
        onSearch={search}
        onEmpty={() => setPrompt('Enter at least one keyword, or choose a department or designation.')}
        onTyping={() => setPrompt(null)}
      />

      {prompt && <Alert kind="warning">{prompt}</Alert>}
      {error && !loading && <Alert>{error.message}</Alert>}

      {!hasQuery && !prompt && (
        <div className="card empty-state">
          <h2>Who are you looking for?</h2>
          <p className="muted">Try a research area like “computer vision”, or browse a department.</p>
        </div>
      )}

      {hasQuery && loading && !data && <Spinner label="Searching…" />}

      {hasQuery && data && (
        <>
          <p className="result-count muted" aria-live="polite">
            {data.total === 0
              ? ''
              : `${data.total} ${data.total === 1 ? 'faculty member' : 'faculty members'} found`}
          </p>

          {data.total === 0 ? (
            // FR-021 / UC-010 alt flows ii-iii
            <div className="card empty-state">
              <h2>No matching profiles</h2>
              <p className="muted">
                {filtered
                  ? 'Nobody matches that combination. Try removing a filter or using a broader keyword.'
                  : 'Try a broader keyword, or check the spelling.'}
              </p>
            </div>
          ) : (
            <ul className={`result-list ${loading ? 'is-loading' : ''}`}>
              {data.results.map((r, i) => {
                const matched = new Set(r.matched_keywords.map((k) => k.toLowerCase()))
                const rest = [...r.expertise_keywords, ...r.research_interests].filter((k) => !matched.has(k.toLowerCase()))
                return (
                  <li key={r.user_id} className="rise" style={{ '--i': i }}>
                    <Link to={`/profiles/${r.user_id}`} className="card result-card">
                      <div className="result-avatar" aria-hidden="true">
                        {r.full_name.replace(/^(dr|prof)\.?\s+/i, '').split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase()}
                      </div>
                      <div className="result-body">
                        <h3>{r.full_name}</h3>
                        <p className="muted small">{[r.designation, r.department?.name].filter(Boolean).join(' · ')}</p>
                        <div className="chips chips-sm">
                          {r.matched_keywords.map((k) => <span key={k} className="chip chip-match">{k}</span>)}
                          {rest.slice(0, 4).map((k) => <span key={k} className="chip">{k}</span>)}
                          {rest.length > 4 && <span className="chip chip-more">+{rest.length - 4}</span>}
                        </div>
                      </div>
                      <span className="result-arrow" aria-hidden="true">→</span>
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}

          {totalPages > 1 && (
            <nav className="pager" aria-label="Pages">
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => goToPage(page - 1)}>← Previous</button>
              <span className="muted small">Page {page} of {totalPages}</span>
              <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => goToPage(page + 1)}>Next →</button>
            </nav>
          )}
        </>
      )}
    </div>
  )
}

function SearchForm({ initial, departments, designations, onSearch, onEmpty, onTyping }) {
  const [form, setForm] = useState(initial)

  function submit(e) {
    e.preventDefault()
    // AC-020: empty search prompts instead of searching
    if (!form.q.trim() && !form.department_id && !form.designation) onEmpty()
    else onSearch(form)
  }

  return (
    <form className="card search-bar rise" onSubmit={submit} noValidate>
      <div className="search-input">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
        <input
          value={form.q}
          onChange={(e) => {
            setForm((f) => ({ ...f, q: e.target.value }))
            onTyping()
          }}
          placeholder="e.g. machine learning, VLSI, medical imaging"
          aria-label="Keywords"
          maxLength={500}
          autoFocus
        />
      </div>
      <select
        value={form.department_id}
        onChange={(e) => setForm((f) => ({ ...f, department_id: e.target.value }))}
        aria-label="Department"
      >
        <option value="">All departments</option>
        {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
      </select>
      <select
        value={form.designation}
        onChange={(e) => setForm((f) => ({ ...f, designation: e.target.value }))}
        aria-label="Designation"
      >
        <option value="">All designations</option>
        {designations.map((d) => <option key={d} value={d}>{d}</option>)}
      </select>
      <button className="btn btn-primary">Search</button>
    </form>
  )
}

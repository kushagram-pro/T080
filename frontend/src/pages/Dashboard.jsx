import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { adminApi, collaborationsApi, profilesApi, suggestionsApi } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { ROLE_LABELS } from '../auth/roles'
import { spotlightHandlers, useCountUp } from '../components/effects'

// Shortcuts to the main tools of each oversight role
const QUICK_LINKS = {
  admin: [
    { to: '/admin/users', title: 'Users', text: 'Create accounts, assign roles, deactivate access.' },
    { to: '/admin/audit', title: 'Audit log', text: 'Every administrative action, newest first.' },
    { to: '/reports', title: 'Activity report', text: 'Collaboration activity across departments.' },
  ],
  research_admin: [
    { to: '/reports', title: 'Collaboration activity', text: 'Totals, trends and expertise across all departments.' },
    { to: '/reports/department', title: 'Department reports', text: 'Faculty, expertise and collaborations per department.' },
    { to: '/search', title: 'Browse faculty', text: 'Search every active faculty profile.' },
  ],
  dept_mgmt: [
    { to: '/reports/department', title: 'My department', text: 'Faculty, expertise and collaboration activity.' },
    { to: '/search', title: 'Browse faculty', text: 'Search faculty profiles by expertise.' },
  ],
}

function StatCard({ label, value, to, linkText, index }) {
  const shown = useCountUp(value)
  return (
    <div className="card stat-card spotlight rise" style={{ '--i': index }} {...spotlightHandlers}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{shown ?? '–'}</span>
      {to && <Link to={to} className="stat-link">{linkText} →</Link>}
    </div>
  )
}

// Faculty: is my profile created, and can colleagues find me? (BR-005)
function ProfileStatusCard({ profile }) {
  if (profile === undefined) return null
  let title, text, cta
  if (profile === null) {
    title = 'Create your profile'
    text = 'Add your expertise and research interests so colleagues can find you.'
    cta = 'Create profile'
  } else if (!profile.is_discoverable) {
    title = 'Finish your profile'
    text = `Not visible in search yet. Missing: ${profile.missing_for_discovery.join(', ')}.`
    cta = 'Complete profile'
  } else {
    title = 'Your profile is live'
    text = `${profile.expertise_keywords.length} expertise · ${profile.publications.length} publications · ${profile.projects.length} projects`
    cta = 'View profile'
  }
  return (
    <div className={`card stat-card spotlight rise profile-status ${profile?.is_discoverable ? 'is-live' : 'needs-work'}`}
      style={{ '--i': 0 }} {...spotlightHandlers}>
      <span className="stat-label">My profile</span>
      <h3>{title}</h3>
      <p className="muted small">{text}</p>
      <Link to="/profile" className="stat-link">{cta} →</Link>
    </div>
  )
}

// FR-024: suggested collaborators with the shared keywords behind each suggestion
function Suggestions({ items }) {
  if (items === undefined) return null
  return (
    <section>
      <h2 className="section-title">Suggested collaborators</h2>
      {items.length === 0 ? (
        <div className="card empty-state">
          <p className="muted">
            No suggestions yet. Adding more expertise and research interests to{' '}
            <Link to="/profile">your profile</Link> helps us find matches.
          </p>
        </div>
      ) : (
        <div className="grid-cards">
          {items.map((s, i) => (
            <Link key={s.user_id} to={`/profiles/${s.user_id}`} className="card feature-card suggestion-card spotlight rise"
              style={{ '--i': i + 2 }} {...spotlightHandlers}>
              <h3>{s.full_name}</h3>
              <p className="muted small">{[s.designation, s.department?.name].filter(Boolean).join(' · ')}</p>
              <span className="shared-label">Shared interests</span>
              <div className="chips chips-sm">
                {s.shared_keywords.map((k) => <span key={k} className="chip chip-match">{k}</span>)}
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const [adminStats, setAdminStats] = useState({})
  const isAdmin = user.role === 'admin'
  const isFaculty = user.role === 'faculty'
  const [myProfile, setMyProfile] = useState(undefined)
  const [suggestions, setSuggestions] = useState(undefined)
  const [collab, setCollab] = useState({})

  useEffect(() => {
    if (!isFaculty) return
    profilesApi
      .getMine()
      .then(setMyProfile)
      .catch((err) => setMyProfile(err.status === 404 ? null : undefined))
    // 404 = no profile yet; the profile card already prompts for that
    suggestionsApi.list(6).then(setSuggestions).catch(() => setSuggestions(undefined))
    Promise.all([collaborationsApi.received(), collaborationsApi.collaborators()])
      .then(([received, collaborators]) =>
        setCollab({ pending: received.filter((r) => r.status === 'pending').length, collaborators: collaborators.length }))
      .catch(() => {})
  }, [isFaculty])

  useEffect(() => {
    if (!isAdmin) return
    let cancelled = false
    // FR-040
    adminApi.dashboard().then((d) => !cancelled && setAdminStats(d)).catch(() => {})
    return () => {
      cancelled = true
    }
  }, [isAdmin])

  const firstName = user.full_name.replace(/^(dr|prof)\.?\s+/i, '').split(' ')[0]

  return (
    <div className="stack-lg">
      <section className="hero">
        <div className="hero-glow" aria-hidden="true" />
        <span className="hero-eyebrow">{ROLE_LABELS[user.role]}</span>
        <h1>
          Welcome back, <span className="gradient-text">{firstName}</span>
        </h1>
        <p>{user.email}</p>
      </section>

      {(isFaculty || isAdmin) && (
      <section className="grid-stats">
        {isFaculty && <ProfileStatusCard profile={myProfile} />}
        {isFaculty && (
          <StatCard index={1} label="Requests waiting for you" value={collab.pending} to="/collaborations" linkText="Respond" />
        )}
        {isFaculty && (
          <StatCard index={2} label="Collaborators" value={collab.collaborators} to="/collaborations?tab=collaborators" linkText="View" />
        )}
        {isAdmin && (
          <>
            <StatCard index={0} label="Registered faculty" value={adminStats.registered_faculty} to="/admin/users?role=faculty" linkText="Manage" />
            <StatCard index={1} label="Active collaborations" value={adminStats.active_collaborations} to="/reports" linkText="Activity report" />
            <StatCard index={2} label="Pending requests" value={adminStats.pending_requests} to="/reports" linkText="Details" />
            <StatCard index={3} label="Pending registrations" value={adminStats.pending_registrations} to="/admin/approvals" linkText="Review" />
            <StatCard index={4} label="Incomplete profiles" value={adminStats.incomplete_profiles} />
            <StatCard index={5} label="Departments" value={adminStats.departments} to="/departments" linkText="Manage" />
          </>
        )}
      </section>
      )}

      {isFaculty && <Suggestions items={suggestions} />}

      {QUICK_LINKS[user.role] && (
        <section>
          <h2 className="section-title">Shortcuts</h2>
          <div className="grid-cards">
            {QUICK_LINKS[user.role].map((f, i) => (
              <Link key={f.to} to={f.to} className="card feature-card quick-link spotlight rise" style={{ '--i': i + 2 }} {...spotlightHandlers}>
                <h3>{f.title} <span aria-hidden="true">→</span></h3>
                <p className="muted">{f.text}</p>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

// Read-only rendering of a profile. Pass the on* handlers to show edit controls (own profile).

function initialsOf(name) {
  return name
    .replace(/^(dr|prof)\.?\s+/i, '')
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

// A DOI becomes a doi.org link; anything else is already an http(s) URL (validated by the backend)
function linkFor(doiOrUrl) {
  return /^10\.\d{4,9}\//.test(doiOrUrl) ? `https://doi.org/${doiOrUrl}` : doiOrUrl
}

function monthYear(iso) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })
}

function Chips({ items, empty }) {
  if (!items.length) return <p className="muted small">{empty}</p>
  return (
    <div className="chips">
      {items.map((k, i) => (
        <span key={k} className="chip rise" style={{ '--i': i }}>{k}</span>
      ))}
    </div>
  )
}

export function ProfileHeader({ profile, onEdit }) {
  return (
    <section className="card profile-header rise">
      <div className="profile-avatar" aria-hidden="true">{initialsOf(profile.full_name)}</div>
      <div className="profile-id">
        <h1>{profile.full_name}</h1>
        <p className="profile-role">
          {[profile.designation, profile.department?.name].filter(Boolean).join(' · ')}
        </p>
        <a className="profile-email" href={`mailto:${profile.email}`}>{profile.email}</a>
      </div>
      {onEdit && (
        <button className="btn btn-ghost profile-edit" onClick={onEdit}>Edit profile</button>
      )}
      {profile.bio && <p className="profile-bio">{profile.bio}</p>}
    </section>
  )
}

export function KeywordSections({ profile }) {
  return (
    <div className="grid-2">
      <section className="card rise" style={{ '--i': 1 }}>
        <h2 className="card-title">Expertise</h2>
        <Chips items={profile.expertise_keywords} empty="No expertise added yet." />
      </section>
      <section className="card rise" style={{ '--i': 2 }}>
        <h2 className="card-title">Research interests</h2>
        <Chips items={profile.research_interests} empty="No research interests added yet." />
      </section>
    </div>
  )
}

function SectionHead({ title, count, onAdd, addLabel }) {
  return (
    <div className="section-head">
      <h2 className="card-title">
        {title} {count > 0 && <span className="count">{count}</span>}
      </h2>
      {onAdd && <button className="btn btn-ghost btn-sm" onClick={onAdd}>+ {addLabel}</button>}
    </div>
  )
}

function RowActions({ onEdit, onDelete }) {
  if (!onEdit) return null
  return (
    <div className="item-actions">
      <button className="btn btn-ghost btn-sm" onClick={onEdit}>Edit</button>
      <button className="btn btn-danger-ghost btn-sm" onClick={onDelete}>Delete</button>
    </div>
  )
}

export function PublicationsSection({ publications, onAdd, onEdit, onDelete }) {
  return (
    <section className="card rise" style={{ '--i': 3 }}>
      <SectionHead title="Publications" count={publications.length} onAdd={onAdd} addLabel="Add publication" />
      {publications.length === 0 ? (
        <p className="muted small">No publications listed.</p>
      ) : (
        <ul className="item-list">
          {publications.map((p) => (
            <li key={p.id} className="item">
              <div className="item-year">{p.year}</div>
              <div className="item-body">
                <h3>
                  {p.doi_url ? (
                    <a href={linkFor(p.doi_url)} target="_blank" rel="noopener noreferrer">{p.title} ↗</a>
                  ) : (
                    p.title
                  )}
                </h3>
                <p className="muted">{p.venue}</p>
              </div>
              <RowActions onEdit={onEdit && (() => onEdit(p))} onDelete={onDelete && (() => onDelete(p))} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export function ProjectsSection({ projects, onAdd, onEdit, onDelete }) {
  return (
    <section className="card rise" style={{ '--i': 4 }}>
      <SectionHead title="Projects" count={projects.length} onAdd={onAdd} addLabel="Add project" />
      {projects.length === 0 ? (
        <p className="muted small">No projects listed.</p>
      ) : (
        <ul className="item-list">
          {projects.map((p) => (
            <li key={p.id} className="item">
              <span className={`status-dot ${p.status}`} title={p.status === 'ongoing' ? 'Ongoing' : 'Past'} />
              <div className="item-body">
                <h3>{p.title}</h3>
                <p className="muted small">
                  {p.status === 'ongoing' ? 'Ongoing' : 'Past'} · {monthYear(p.start_date)} –{' '}
                  {p.end_date ? monthYear(p.end_date) : 'present'}
                </p>
                {p.description && <p className="item-desc">{p.description}</p>}
              </div>
              <RowActions onEdit={onEdit && (() => onEdit(p))} onDelete={onDelete && (() => onDelete(p))} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

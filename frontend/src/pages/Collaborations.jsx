import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { announceNotificationsChanged, collaborationsApi } from '../api/endpoints'
import { Alert, Modal, Spinner } from '../components/ui'
import { timeAgo } from '../utils/format'

const TABS = [
  { id: 'received', label: 'Received' },
  { id: 'sent', label: 'Sent' },
  { id: 'collaborators', label: 'My collaborators' },
]

const STATUS_LABEL = { pending: 'Pending', accepted: 'Accepted', declined: 'Declined', withdrawn: 'Withdrawn' }

function initials(name) {
  return name.replace(/^(dr|prof)\.?\s+/i, '').split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase()
}

function Person({ other }) {
  return (
    <Link to={`/profiles/${other.user_id}`} className="person">
      <span className="person-avatar" aria-hidden="true">{initials(other.full_name)}</span>
      <span className="person-text">
        <strong>{other.full_name}</strong>
        <span className="muted small">{[other.designation, other.department].filter(Boolean).join(' · ')}</span>
      </span>
    </Link>
  )
}

export default function Collaborations() {
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState({ received: null, sent: null, collaborators: null })

  // ?request=ID (from a notification): open whichever tab holds that request and highlight it
  const focusId = Number(params.get('request')) || null
  const explicitTab = TABS.some((t) => t.id === params.get('tab')) ? params.get('tab') : null
  const tab = explicitTab ?? (focusId && data.sent?.some((r) => r.id === focusId) ? 'sent' : 'received')

  useEffect(() => {
    if (!focusId || !data.sent) return
    document.getElementById(`request-${focusId}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [focusId, data.sent])
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [confirm, setConfirm] = useState(null) // { kind: 'decline'|'withdraw', req }

  const load = () =>
    Promise.all([collaborationsApi.received(), collaborationsApi.sent(), collaborationsApi.collaborators()])
      .then(([received, sent, collaborators]) => setData({ received, sent, collaborators }))
      .catch((err) => setError(err.message))

  useEffect(() => {
    load()
  }, [])

  async function act(req, kind) {
    setBusyId(req.id)
    setError(null)
    try {
      if (kind === 'accept') await collaborationsApi.accept(req.id)
      if (kind === 'decline') await collaborationsApi.decline(req.id)
      if (kind === 'withdraw') await collaborationsApi.withdraw(req.id)
      await load()
      setNotice(
        kind === 'accept'
          ? `You're now collaborating with ${req.other.full_name}.`
          : kind === 'decline'
            ? `Declined ${req.other.full_name}'s request.`
            : `Withdrew your request to ${req.other.full_name}.`,
      )
      announceNotificationsChanged()
    } catch (err) {
      setError(err.message)
      await load() // e.g. it was already answered elsewhere: show the real state
    } finally {
      setBusyId(null)
      setConfirm(null)
    }
  }

  const pendingReceived = data.received?.filter((r) => r.status === 'pending').length ?? 0
  const counts = {
    received: pendingReceived,
    sent: data.sent?.filter((r) => r.status === 'pending').length ?? 0,
    collaborators: data.collaborators?.length ?? 0,
  }

  // Pending first, then newest
  const sortRequests = (list) =>
    [...list].sort((a, b) => (a.status === 'pending') === (b.status === 'pending') ? 0 : a.status === 'pending' ? -1 : 1)

  const list = data[tab]

  return (
    <div className="stack-lg">
      <section className="page-header">
        <div>
          <h1>Collaborations</h1>
          <p className="muted">Requests you've received and sent, and the colleagues you collaborate with.</p>
        </div>
        <Link to="/search" className="btn btn-ghost">Find collaborators</Link>
      </section>

      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            className={`tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => setParams(t.id === 'received' ? {} : { tab: t.id })}
          >
            {t.label}
            {counts[t.id] > 0 && <span className="tab-count">{counts[t.id]}</span>}
          </button>
        ))}
      </div>

      {notice && <Alert kind="success">{notice}</Alert>}
      {error && <Alert>{error}</Alert>}

      {list === null && !error && <Spinner />}

      {list?.length === 0 && (
        <div className="card empty-state">
          <h2>
            {tab === 'received' ? 'No requests yet' : tab === 'sent' ? 'You haven’t sent any requests' : 'No collaborators yet'}
          </h2>
          <p className="muted">
            {tab === 'collaborators'
              ? 'When a request is accepted, you’ll both appear here.'
              : 'Search for colleagues by expertise and send them a request from their profile.'}
          </p>
          {tab !== 'received' && <Link to="/search" className="btn btn-primary">Find collaborators</Link>}
        </div>
      )}

      {list?.length > 0 && tab !== 'collaborators' && (
        <ul className="request-list" key={tab}>
          {sortRequests(list).map((r, i) => (
            <li key={r.id} id={`request-${r.id}`} style={{ '--i': i }}
              className={`card request-item rise ${r.status} ${r.id === focusId ? 'is-focused' : ''}`}>
              <div className="request-head">
                <Person other={r.other} />
                <span className={`status-pill ${r.status}`}>{STATUS_LABEL[r.status]}</span>
              </div>
              {r.message && <blockquote className="request-message">{r.message}</blockquote>}
              <div className="request-foot">
                <span className="muted small">
                  {tab === 'received' ? 'Received' : 'Sent'} {timeAgo(r.sent_at)}
                  {r.responded_at && r.status !== 'pending' && ` · ${STATUS_LABEL[r.status].toLowerCase()} ${timeAgo(r.responded_at)}`}
                </span>
                {r.status === 'pending' && tab === 'received' && (
                  <div className="row-actions">
                    <button className="btn btn-ghost btn-sm" disabled={busyId === r.id} onClick={() => setConfirm({ kind: 'decline', req: r })}>
                      Decline
                    </button>
                    <button className="btn btn-primary btn-sm" disabled={busyId === r.id} onClick={() => act(r, 'accept')}>
                      Accept
                    </button>
                  </div>
                )}
                {r.status === 'pending' && tab === 'sent' && (
                  <button className="btn btn-danger-ghost btn-sm" disabled={busyId === r.id} onClick={() => setConfirm({ kind: 'withdraw', req: r })}>
                    Withdraw
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {list?.length > 0 && tab === 'collaborators' && (
        <ul className="grid-cards collaborator-grid" key={tab}>
          {list.map((c, i) => (
            <li key={c.collaboration_id} className="card collaborator-card rise" style={{ '--i': i }}>
              <Person other={c.other} />
              <span className="muted small">Collaborating since {timeAgo(c.since)}</span>
            </li>
          ))}
        </ul>
      )}

      <Modal
        open={confirm !== null}
        title={confirm?.kind === 'decline' ? `Decline ${confirm?.req.other.full_name}'s request?` : 'Withdraw this request?'}
        onClose={() => setConfirm(null)}
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setConfirm(null)}>Cancel</button>
            <button className="btn btn-danger" disabled={busyId !== null} onClick={() => act(confirm.req, confirm.kind)}>
              {confirm?.kind === 'decline' ? 'Decline' : 'Withdraw'}
            </button>
          </>
        }
      >
        <p className="muted">
          {confirm?.kind === 'decline'
            ? `${confirm?.req.other.full_name} will be notified. They can send a new request later.`
            : `${confirm?.req.other.full_name} won't be able to respond to it any more.`}
        </p>
      </Modal>
    </div>
  )
}

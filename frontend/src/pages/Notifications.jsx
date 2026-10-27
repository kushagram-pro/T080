import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { announceNotificationsChanged, notificationsApi } from '../api/endpoints'
import { Alert, Spinner } from '../components/ui'
import { timeAgo } from '../utils/format'
import { notificationTarget } from '../utils/notifications'

const PAGE_SIZE = 20

// FR-037: full history, newest first. FR-036: mark as read.
export default function Notifications() {
  const [items, setItems] = useState(null)
  const [meta, setMeta] = useState({ total: 0, unread: 0, page: 1 })
  const [error, setError] = useState(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    notificationsApi
      .list(1, PAGE_SIZE)
      .then((p) => {
        setItems(p.results)
        setMeta({ total: p.total, unread: p.unread_count, page: 1 })
      })
      .catch((err) => setError(err.message))
  }, [])

  async function loadMore() {
    setLoadingMore(true)
    try {
      const p = await notificationsApi.list(meta.page + 1, PAGE_SIZE)
      setItems((list) => [...list, ...p.results])
      setMeta((m) => ({ ...m, page: m.page + 1, total: p.total }))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoadingMore(false)
    }
  }

  async function markAll() {
    await notificationsApi.markAllRead()
    setItems((list) => list.map((n) => ({ ...n, is_read: true })))
    setMeta((m) => ({ ...m, unread: 0 }))
    announceNotificationsChanged()
  }

  async function markOne(n) {
    if (n.is_read) return
    await notificationsApi.markRead(n.id)
    setItems((list) => list.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)))
    setMeta((m) => ({ ...m, unread: Math.max(0, m.unread - 1) }))
    announceNotificationsChanged()
  }

  return (
    <div className="stack-lg">
      <section className="page-header">
        <div>
          <h1>Notifications</h1>
          <p className="muted">{meta.unread ? `${meta.unread} unread` : 'Everything is read.'}</p>
        </div>
        {meta.unread > 0 && <button className="btn btn-ghost" onClick={markAll}>Mark all as read</button>}
      </section>

      {error && <Alert>{error}</Alert>}
      {items === null && !error && <Spinner />}

      {items?.length === 0 && (
        <div className="card empty-state">
          <h2>No notifications yet</h2>
          <p className="muted">You'll be notified when someone sends you a request or answers yours.</p>
        </div>
      )}

      {items?.length > 0 && (
        <ul className="card notification-list">
          {items.map((n, i) => (
            <li key={n.id} className={`notification ${n.is_read ? '' : 'unread'} rise`} style={{ '--i': Math.min(i, 10) }}>
              <span className="bell-dot" aria-hidden="true" />
              <button className="notification-body" onClick={() => markOne(n).then(() => navigate(notificationTarget(n)))}>
                <span>{n.message}</span>
                <span className="muted small">{timeAgo(n.created_at)}</span>
              </button>
              {!n.is_read && (
                <button className="link-button small" onClick={() => markOne(n)}>Mark as read</button>
              )}
            </li>
          ))}
        </ul>
      )}

      {items && items.length < meta.total && (
        <button className="btn btn-ghost" style={{ alignSelf: 'center' }} disabled={loadingMore} onClick={loadMore}>
          {loadingMore ? 'Loading…' : 'Load older notifications'}
        </button>
      )}
    </div>
  )
}

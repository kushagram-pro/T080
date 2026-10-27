import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { NOTIFICATIONS_CHANGED, notificationsApi } from '../api/endpoints'
import { timeAgo } from '../utils/format'
import { notificationTarget } from '../utils/notifications'

const POLL_MS = 30_000

export function NotificationBell() {
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState(null)
  const ref = useRef(null)
  const navigate = useNavigate()

  const refreshCount = useCallback(() => {
    notificationsApi.unreadCount().then((r) => setUnread(r.unread_count)).catch(() => {})
  }, [])

  // Poll while the tab is visible; refresh immediately when it regains focus or something changes
  useEffect(() => {
    refreshCount()
    const timer = window.setInterval(() => document.visibilityState === 'visible' && refreshCount(), POLL_MS)
    window.addEventListener('focus', refreshCount)
    window.addEventListener(NOTIFICATIONS_CHANGED, refreshCount)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('focus', refreshCount)
      window.removeEventListener(NOTIFICATIONS_CHANGED, refreshCount)
    }
  }, [refreshCount])

  // Close on outside click / Escape
  useEffect(() => {
    if (!open) return
    const onClick = (e) => !ref.current?.contains(e.target) && setOpen(false)
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  async function toggle() {
    const next = !open
    setOpen(next)
    if (next) {
      try {
        const page = await notificationsApi.list(1, 8)
        setItems(page.results)
        setUnread(page.unread_count)
      } catch {
        setItems([])
      }
    }
  }

  async function openItem(n) {
    setOpen(false)
    if (!n.is_read) {
      await notificationsApi.markRead(n.id).catch(() => {})
      refreshCount()
    }
    navigate(notificationTarget(n))
  }

  async function markAll() {
    await notificationsApi.markAllRead().catch(() => {})
    setItems((list) => list?.map((n) => ({ ...n, is_read: true })))
    setUnread(0)
  }

  return (
    <div className="bell" ref={ref}>
      <button
        className="theme-toggle bell-button"
        onClick={toggle}
        aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-expanded={open}
        aria-haspopup="true"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        {unread > 0 && <span className="bell-badge" key={unread}>{unread > 9 ? '9+' : unread}</span>}
      </button>

      {open && (
        <div className="bell-panel" role="menu">
          <div className="bell-head">
            <strong>Notifications</strong>
            {unread > 0 && <button className="link-button" onClick={markAll}>Mark all as read</button>}
          </div>
          {items === null ? (
            <p className="muted small bell-empty">Loading…</p>
          ) : items.length === 0 ? (
            <p className="muted small bell-empty">You're all caught up.</p>
          ) : (
            <ul>
              {items.map((n, i) => (
                <li key={n.id} style={{ '--i': i }}>
                  <button className={`bell-item ${n.is_read ? '' : 'unread'}`} onClick={() => openItem(n)} role="menuitem">
                    <span className="bell-dot" aria-hidden="true" />
                    <span className="bell-text">
                      {n.message}
                      <span className="muted small">{timeAgo(n.created_at)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <Link to="/notifications" className="bell-all" onClick={() => setOpen(false)}>See all notifications</Link>
        </div>
      )}
    </div>
  )
}

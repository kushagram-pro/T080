import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { announceNotificationsChanged, collaborationsApi } from '../../api/endpoints'
import { Alert, Modal, Spinner } from '../ui'
import { formatDate } from '../../utils/format'

const MAX = 2000
const POLL_MS = 10000

// Conversation with one collaborator. Polls for new messages while open; ended
// collaborations (or a deactivated partner) are read-only.
export function ChatPanel({ collaboration, onClose, onRead }) {
  const id = collaboration.collaboration_id
  const [thread, setThread] = useState(null)
  const [error, setError] = useState(null)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const listRef = useRef(null)
  const stickToBottom = useRef(true)

  const markRead = useCallback(() => {
    collaborationsApi.markMessagesRead(id).then(() => {
      onRead?.()
      announceNotificationsChanged()
    }).catch(() => {})
  }, [id, onRead])

  useEffect(() => {
    let cancelled = false
    collaborationsApi
      .messages(id)
      .then((t) => {
        if (cancelled) return
        setThread(t)
        markRead()
      })
      .catch((err) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [id, markRead])

  // Poll for newer messages
  useEffect(() => {
    if (!thread) return
    const timer = window.setInterval(async () => {
      const last = thread.messages.at(-1)?.id
      try {
        const t = await collaborationsApi.messages(id, last ? { after_id: last } : {})
        if (t.messages.length) {
          setThread((cur) => ({ ...t, messages: [...cur.messages, ...t.messages], has_more: cur.has_more }))
          markRead()
        } else if (t.can_send !== thread.can_send) {
          setThread((cur) => ({ ...cur, can_send: t.can_send, ended_at: t.ended_at }))
        }
      } catch {
        // keep the conversation on screen; the next poll may succeed
      }
    }, POLL_MS)
    return () => window.clearInterval(timer)
  }, [id, thread, markRead])

  // Keep the newest message in view unless the reader has scrolled up
  useLayoutEffect(() => {
    const el = listRef.current
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight
  }, [thread?.messages.length])

  async function loadOlder() {
    const el = listRef.current
    const before = el?.scrollHeight ?? 0
    setLoadingOlder(true)
    try {
      const t = await collaborationsApi.messages(id, { before_id: thread.messages[0].id })
      stickToBottom.current = false
      setThread((cur) => ({ ...cur, messages: [...t.messages, ...cur.messages], has_more: t.has_more }))
      requestAnimationFrame(() => {
        if (el) el.scrollTop = el.scrollHeight - before // stay where the reader was
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoadingOlder(false)
    }
  }

  async function send(e) {
    e.preventDefault()
    const body = draft.trim()
    if (!body) return
    setSending(true)
    setError(null)
    try {
      const msg = await collaborationsApi.sendMessage(id, body)
      stickToBottom.current = true
      setThread((cur) => ({ ...cur, messages: [...cur.messages, msg] }))
      setDraft('')
    } catch (err) {
      setError(err.message)
      if (err.status === 409) setThread((cur) => ({ ...cur, can_send: false }))
    } finally {
      setSending(false)
    }
  }

  const name = collaboration.other.full_name
  const lastMine = thread?.messages.findLast((m) => m.mine)

  return (
    <Modal
      open
      wide
      title={name}
      onClose={onClose}
      footer={<button className="btn btn-ghost" onClick={onClose}>Close</button>}
    >
      {error && <Alert>{error}</Alert>}
      {!thread && !error && <Spinner />}
      {thread && (
        <>
          <div
            className="chat-list"
            ref={listRef}
            onScroll={(e) => {
              const el = e.currentTarget
              stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40
            }}
            aria-live="polite"
          >
            {thread.has_more && (
              <button className="btn btn-ghost btn-sm chat-older" disabled={loadingOlder} onClick={loadOlder}>
                {loadingOlder ? 'Loading…' : 'Load earlier messages'}
              </button>
            )}
            {thread.messages.length === 0 && (
              <p className="muted small chat-empty">No messages yet. Say hello to {name}.</p>
            )}
            {thread.messages.map((m) => (
              <div key={m.id} className={`chat-msg ${m.mine ? 'mine' : 'theirs'}`}>
                <p>{m.body}</p>
                <span className="chat-meta">
                  {formatDate(m.created_at)}
                  {m.id === lastMine?.id && m.read_at && ' · Seen'}
                </span>
              </div>
            ))}
          </div>

          {thread.can_send ? (
            <form className="chat-compose" onSubmit={send}>
              <textarea
                rows={2}
                maxLength={MAX}
                value={draft}
                placeholder={`Message ${name}`}
                aria-label={`Message ${name}`}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  // Enter sends, Shift+Enter adds a line
                  if (e.key === 'Enter' && !e.shiftKey) send(e)
                }}
                autoFocus
              />
              <button className="btn btn-primary" disabled={sending || !draft.trim()}>
                {sending ? 'Sending…' : 'Send'}
              </button>
            </form>
          ) : (
            <p className="muted small chat-closed">
              {thread.ended_at
                ? 'This collaboration has ended. You can still read the conversation.'
                : `${name}'s account is no longer active, so new messages can't be sent.`}
            </p>
          )}
        </>
      )}
    </Modal>
  )
}

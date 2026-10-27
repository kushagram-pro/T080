import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { announceNotificationsChanged, collaborationsApi } from '../../api/endpoints'
import { Alert, Field, Modal } from '../ui'

const MESSAGE_MAX = 500 // FR-027

// Shown on another faculty member's profile: Send / Withdraw / Accept-Decline / Collaborating
export function RequestActions({ userId, name }) {
  const [rel, setRel] = useState(null) // { state, request_id }
  const [composing, setComposing] = useState(false)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [modalError, setModalError] = useState(null)
  const [notice, setNotice] = useState(null)

  useEffect(() => {
    collaborationsApi.relationship(userId).then(setRel).catch(() => setRel({ state: 'none' }))
  }, [userId])

  async function run(action, nextState, text) {
    setBusy(true)
    setError(null)
    try {
      const req = await action()
      setRel({ state: nextState, request_id: nextState.startsWith('pending') ? req.id : null })
      setNotice(text)
      announceNotificationsChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function send() {
    setBusy(true)
    setModalError(null)
    try {
      const req = await collaborationsApi.send(userId, message.trim())
      setRel({ state: 'pending_sent', request_id: req.id })
      setComposing(false)
      setMessage('')
      setNotice(`Request sent. ${name} has been notified.`) // AC-008
    } catch (err) {
      setModalError(err.message) // AC-010: clear message, nothing created
    } finally {
      setBusy(false)
    }
  }

  if (!rel) return null

  return (
    <div className="request-actions rise">
      {notice && <Alert kind="success">{notice}</Alert>}
      {error && <Alert>{error}</Alert>}

      <div className="request-bar card">
        {rel.state === 'none' && (
          <>
            <div>
              <h3>Interested in working together?</h3>
              <p className="muted small">Send {name} a collaboration request with an optional note.</p>
            </div>
            <button className="btn btn-primary" onClick={() => setComposing(true)}>Send collaboration request</button>
          </>
        )}

        {rel.state === 'pending_sent' && (
          <>
            <div>
              <span className="status-pill pending">Request pending</span>
              <p className="muted small">Waiting for {name} to respond.</p>
            </div>
            <button className="btn btn-danger-ghost" disabled={busy}
              onClick={() => run(() => collaborationsApi.withdraw(rel.request_id), 'none', 'Request withdrawn.')}>
              Withdraw request
            </button>
          </>
        )}

        {rel.state === 'pending_received' && (
          <>
            <div>
              <h3>{name} wants to collaborate with you</h3>
              <p className="muted small">
                See their note under <Link to="/collaborations">Collaborations</Link>.
              </p>
            </div>
            <div className="row-actions">
              <button className="btn btn-ghost" disabled={busy}
                onClick={() => run(() => collaborationsApi.decline(rel.request_id), 'none', 'Request declined.')}>
                Decline
              </button>
              <button className="btn btn-primary" disabled={busy}
                onClick={() => run(() => collaborationsApi.accept(rel.request_id), 'collaborators', `You're now collaborating with ${name}.`)}>
                Accept
              </button>
            </div>
          </>
        )}

        {rel.state === 'collaborators' && (
          <div className="collab-badge">
            <span className="collab-check" aria-hidden="true">✓</span>
            <div>
              <h3>Collaborating</h3>
              <p className="muted small">You and {name} are collaborators.</p>
            </div>
          </div>
        )}
      </div>

      <Modal
        open={composing}
        title={`Send a request to ${name}`}
        onClose={() => setComposing(false)}
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setComposing(false)}>Cancel</button>
            <button className="btn btn-primary" disabled={busy} onClick={send}>{busy ? 'Sending…' : 'Send request'}</button>
          </>
        }
      >
        <Alert>{modalError}</Alert>
        <Field label="Message" hint={`${message.length}/${MESSAGE_MAX} · optional`}>
          <textarea
            rows={5}
            maxLength={MESSAGE_MAX}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Say what you'd like to work on together."
            autoFocus
          />
        </Field>
      </Modal>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { approvalsApi } from '../api/endpoints'
import { Alert, Field, Modal, Spinner } from '../components/ui'
import { formatDate } from '../utils/format'

const REASON_MAX = 500

export default function Approvals() {
  const [pending, setPending] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [rejecting, setRejecting] = useState(null) // user being rejected
  const [reason, setReason] = useState('')
  const [rejectError, setRejectError] = useState(null)

  useEffect(() => {
    approvalsApi.listPending().then(setPending).catch((err) => setLoadError(err.message))
  }, [])

  function removeFromList(id) {
    setPending((list) => list.filter((u) => u.id !== id))
  }

  async function approve(user) {
    setBusyId(user.id)
    setNotice(null)
    try {
      await approvalsApi.approve(user.id)
      removeFromList(user.id)
      setNotice({ kind: 'success', text: `${user.full_name} approved. They've been emailed and can now log in.` })
    } catch (err) {
      if (err.status === 409) removeFromList(user.id) // someone else already handled it
      setNotice({ kind: 'error', text: err.message })
    } finally {
      setBusyId(null)
    }
  }

  function openReject(user) {
    setRejecting(user)
    setReason('')
    setRejectError(null)
  }

  async function confirmReject() {
    if (!reason.trim()) {
      setRejectError('Please give a reason. It is included in the email to the applicant.')
      return
    }
    const user = rejecting
    setBusyId(user.id)
    try {
      await approvalsApi.reject(user.id, reason.trim())
      removeFromList(user.id)
      setRejecting(null)
      setNotice({ kind: 'success', text: `${user.full_name}'s registration was rejected and they've been emailed.` })
    } catch (err) {
      if (err.status === 409) {
        removeFromList(user.id)
        setRejecting(null)
        setNotice({ kind: 'error', text: err.message })
      } else {
        setRejectError(err.message)
      }
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="stack-lg">
      <section className="page-header">
        <div>
          <h1>Registration approvals</h1>
          <p className="muted">New faculty accounts wait here until an administrator approves them.</p>
        </div>
      </section>

      {notice && <Alert kind={notice.kind}>{notice.text}</Alert>}
      <Alert>{loadError}</Alert>

      {pending === null && !loadError && <Spinner />}

      {pending?.length === 0 && (
        <div className="card empty-state">
          <h2>All caught up</h2>
          <p className="muted">No registrations are waiting for approval.</p>
        </div>
      )}

      {pending?.length > 0 && (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Submitted</th>
                <th className="col-actions"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {pending.map((u, i) => (
                <tr key={u.id} className="rise" style={{ '--i': i }}>
                  <td data-label="Name" className="strong">{u.full_name}</td>
                  <td data-label="Email">{u.email}</td>
                  <td data-label="Submitted">
                    {formatDate(u.submitted_at)}
                    {u.submitted_at !== u.created_at && <span className="badge badge-muted">Re-applied</span>}
                  </td>
                  <td className="col-actions">
                    <div className="row-actions">
                      <button className="btn btn-primary btn-sm" disabled={busyId === u.id} onClick={() => approve(u)}>
                        Approve
                      </button>
                      <button className="btn btn-danger-ghost btn-sm" disabled={busyId === u.id} onClick={() => openReject(u)}>
                        Reject
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={rejecting !== null}
        title={`Reject ${rejecting?.full_name ?? ''}?`}
        onClose={() => setRejecting(null)}
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setRejecting(null)}>Cancel</button>
            <button className="btn btn-danger" disabled={busyId !== null} onClick={confirmReject}>
              {busyId !== null ? 'Rejecting…' : 'Reject registration'}
            </button>
          </>
        }
      >
        <p className="muted">
          The applicant will be emailed this reason. They can register again with corrected details.
        </p>
        <Field label="Reason" error={rejectError} hint={`${reason.length}/${REASON_MAX}`}>
          <textarea
            rows={4}
            maxLength={REASON_MAX}
            value={reason}
            onChange={(e) => {
              setReason(e.target.value)
              setRejectError(null)
            }}
            placeholder="e.g. This email does not belong to a faculty member."
            autoFocus
          />
        </Field>
      </Modal>
    </div>
  )
}

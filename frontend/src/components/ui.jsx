import { useEffect, useId, useRef } from 'react'

export function Field({ label, error, hint, children }) {
  return (
    <label className={`field ${error ? 'has-error' : ''}`}>
      <span className="field-label">{label}</span>
      {children}
      {error ? <span className="field-error">{error}</span> : hint && <span className="field-hint">{hint}</span>}
    </label>
  )
}

export function Alert({ kind = 'error', children }) {
  if (!children) return null
  return (
    <div className={`alert alert-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  )
}

// Accessible modal dialog built on the native <dialog> element
export function Modal({ open, title, onClose, children, footer }) {
  const ref = useRef(null)
  const titleId = useId()

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      className="modal"
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault()
        onClose()
      }}
    >
      {open && (
        <>
          <h3 id={titleId}>{title}</h3>
          <div className="modal-body">{children}</div>
          <div className="modal-footer">{footer}</div>
        </>
      )}
    </dialog>
  )
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="spinner-row">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}


import { useState } from 'react'

// "Download CSV" for a report; shows its own error if the download fails
export function DownloadButton({ onDownload, label = 'Download CSV' }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function run() {
    setBusy(true)
    setError(null)
    try {
      await onDownload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="download">
      <button className="btn btn-ghost" disabled={busy} onClick={run}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11m0 0-4-4m4 4 4-4M5 19h14" /></svg>
        {busy ? 'Preparing…' : label}
      </button>
      {error && <span className="field-error">{error}</span>}
    </div>
  )
}

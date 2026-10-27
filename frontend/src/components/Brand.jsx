import { useState } from 'react'

// Put the official logo at frontend/public/lnmiit-logo.jpg.
// Until it exists, an "LNM" monogram is shown so nothing looks broken.
const LOGO_SRC = '/lnmiit-logo.jpg'

export function LnmiitLogo({ size = 36, className = '' }) {
  const [failed, setFailed] = useState(false)

  if (failed) {
    return (
      <span className={`logo-fallback ${className}`} style={{ width: size, height: size, fontSize: size * 0.3 }} aria-label="LNMIIT">
        LNM
      </span>
    )
  }
  return (
    <img
      src={LOGO_SRC}
      alt="LNMIIT Jaipur"
      width={size}
      height={size}
      className={`logo-img ${className}`}
      onError={() => setFailed(true)}
    />
  )
}

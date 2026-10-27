import { useEffect, useLayoutEffect, useState } from 'react'

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// Animate a number from 0 up to `target` (ease-out). Returns the current value.
export function useCountUp(target, duration = 900) {
  const [value, setValue] = useState(0)
  const instant = reducedMotion()

  useEffect(() => {
    if (target == null || instant) return
    let frame
    const start = performance.now()
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration)
      setValue(Math.round(target * (1 - Math.pow(1 - t, 3))))
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, duration, instant])

  if (target == null) return null
  return instant ? target : value
}

// Spread onto an element to give it a glow that follows the cursor (see .spotlight in CSS)
export const spotlightHandlers = {
  onPointerMove(e) {
    const r = e.currentTarget.getBoundingClientRect()
    e.currentTarget.style.setProperty('--mx', `${e.clientX - r.left}px`)
    e.currentTarget.style.setProperty('--my', `${e.clientY - r.top}px`)
  },
}

// Position of the active link inside a nav, so a highlight pill can slide to it
export function useActiveIndicator(navRef, dependency) {
  const [rect, setRect] = useState(null)

  useLayoutEffect(() => {
    const measure = () => {
      const active = navRef.current?.querySelector('a.active')
      setRect(active ? { left: active.offsetLeft, width: active.offsetWidth } : null)
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [navRef, dependency])

  return rect
}

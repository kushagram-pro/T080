const KEY = 'fcn-theme'

export function currentTheme() {
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark'
}

function savedTheme() {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function applyTheme(theme, { persist = true } = {}) {
  document.documentElement.dataset.theme = theme
  if (persist) {
    try {
      localStorage.setItem(KEY, theme)
    } catch {
      // Private mode / blocked storage: the theme still applies for this visit
    }
  }
}

// Follow OS theme changes until the user picks one explicitly
export function followSystemTheme(onChange) {
  const mq = window.matchMedia('(prefers-color-scheme: light)')
  const handler = (e) => {
    if (savedTheme()) return
    applyTheme(e.matches ? 'light' : 'dark', { persist: false })
    onChange(currentTheme())
  }
  mq.addEventListener('change', handler)
  return () => mq.removeEventListener('change', handler)
}

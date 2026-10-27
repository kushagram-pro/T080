export function formatDate(iso) {
  // Backend sends naive UTC timestamps; mark them as UTC before formatting
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function parseUtc(iso) {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
}

// "just now", "5 min ago", "3 h ago", "2 days ago", then a plain date
export function timeAgo(iso) {
  const seconds = Math.round((Date.now() - parseUtc(iso).getTime()) / 1000)
  if (seconds < 45) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days} day${days === 1 ? '' : 's'} ago`
  return parseUtc(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

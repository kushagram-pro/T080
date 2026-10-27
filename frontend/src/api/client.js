// Thin fetch wrapper around the FastAPI backend.
//
// Auth model (agreed with the backend):
//  - The access token lives ONLY in this module's memory, never in localStorage.
//  - The refresh token is an httpOnly cookie the browser sends to /auth/* on its own,
//    so every request uses credentials: 'include'.
//  - On a 401 we try one silent refresh, then retry the request once.

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

let accessToken = null
let onAuthLost = () => {}
let refreshing = null

export function setAccessToken(token) {
  accessToken = token
}

export function setOnAuthLost(fn) {
  onAuthLost = fn
}

export class ApiError extends Error {
  constructor(status, message, fieldErrors = {}) {
    super(message)
    this.status = status
    this.fieldErrors = fieldErrors // { fieldName: "message" } for 422 validation errors
  }
}

// Exchange the refresh cookie for a new access token.
// Concurrent callers share one request, so the rotated cookie isn't raced.
export function refreshSession() {
  if (!refreshing) {
    refreshing = fetch(`${API_URL}/auth/refresh`, { method: 'POST', credentials: 'include' })
      .then(async (res) => {
        if (!res.ok) return null
        const data = await res.json()
        accessToken = data.access_token
        return data // { access_token, token_type, user }
      })
      .catch(() => null)
      .finally(() => {
        refreshing = null
      })
  }
  return refreshing
}

function toApiError(status, data) {
  // slowapi rate limit
  if (status === 429) {
    return new ApiError(429, 'Too many attempts. Please wait a minute and try again.')
  }
  const detail = data?.detail
  // FastAPI/Pydantic validation errors: [{ loc: ['body', 'password'], msg: '...' }]
  if (Array.isArray(detail)) {
    const fieldErrors = {}
    for (const err of detail) {
      const field = err.loc?.[err.loc.length - 1]
      const msg = String(err.msg ?? 'Invalid value').replace(/^Value error, /, '')
      if (field && !(field in fieldErrors)) fieldErrors[field] = msg
    }
    const first = Object.values(fieldErrors)[0] ?? 'Please check the form and try again.'
    return new ApiError(status, first, fieldErrors)
  }
  if (typeof detail === 'string') return new ApiError(status, detail)
  return new ApiError(status, 'Something went wrong. Please try again.')
}

export async function api(path, { method = 'GET', body, auth = true, retry = true } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth && accessToken) headers.Authorization = `Bearer ${accessToken}`

  let res
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: 'include',
    })
  } catch {
    throw new ApiError(0, "Can't reach the server. Is the backend running?")
  }

  if (res.status === 401 && auth && retry) {
    const session = await refreshSession()
    if (session) return api(path, { method, body, auth, retry: false })
    onAuthLost()
  }

  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) throw toApiError(res.status, data)
  return data
}

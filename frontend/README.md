# Faculty Collaboration Network — Frontend

React 19 + Vite + React Router. No UI library; styling is plain CSS in `src/index.css`.

## Run

```bash
npm install
cp .env.example .env      # first time only
npm run dev               # http://localhost:5173
```

The backend must be running on http://localhost:8000 (see `../backend`).

## Structure

| Path | What it is |
|---|---|
| `src/api/client.js` | fetch wrapper: in-memory access token, refresh cookie, one silent retry on 401 |
| `src/api/endpoints.js` | one function per backend endpoint |
| `src/auth/` | login state (`AuthContext`), route guards, role labels |
| `src/components/` | layout, LNMIIT logo, theme toggle, modal/field/alert, animation hooks |
| `src/pages/` | Login, Register, Dashboard, Approvals (admin), Departments |
| `public/lnmiit-logo.jpg` | logo used in the top bar and on the login/register pages |

## Auth rules (must match the backend)

- Never put the access token in localStorage. It lives in memory only.
- Every request uses `credentials: 'include'` so the httpOnly refresh cookie is sent.
- Call the backend directly at `VITE_API_URL`, not through a `/api` proxy: the refresh cookie is scoped to the backend's `/auth` path.

## Theme

Dark/light is a `data-theme` attribute on `<html>`, set before first paint by a script in `index.html`
(saved choice, otherwise the OS setting). Colours are CSS variables at the top of `index.css`.

import { api } from './client'

// One function per backend endpoint, so pages never build URLs themselves.

export const authApi = {
  register: (data) => api('/auth/register', { method: 'POST', body: data, auth: false }),
  login: (email, password) => api('/auth/login', { method: 'POST', body: { email, password }, auth: false }),
  logout: () => api('/auth/logout', { method: 'POST', auth: false }),
  me: () => api('/auth/me'),
  forgotPassword: (email) => api('/auth/forgot-password', { method: 'POST', body: { email }, auth: false }),
  resetPassword: (token, newPassword) =>
    api('/auth/reset-password', { method: 'POST', body: { token, new_password: newPassword }, auth: false }),
}

export const approvalsApi = {
  listPending: () => api('/admin/approvals'),
  approve: (userId) => api(`/admin/approvals/${userId}/approve`, { method: 'POST' }),
  reject: (userId, reason) => api(`/admin/approvals/${userId}/reject`, { method: 'POST', body: { reason } }),
}

export const departmentsApi = {
  list: () => api('/departments'),
  create: (data) => api('/departments', { method: 'POST', body: data }),
  update: (id, data) => api(`/departments/${id}`, { method: 'PATCH', body: data }),
  remove: (id) => api(`/departments/${id}`, { method: 'DELETE' }),
}

export const profilesApi = {
  designations: () => api('/profiles/designations'),
  getMine: () => api('/profiles/me'),
  createMine: (data) => api('/profiles/me', { method: 'POST', body: data }),
  updateMine: (data) => api('/profiles/me', { method: 'PATCH', body: data }),
  get: (userId) => api(`/profiles/${userId}`),

  addPublication: (data) => api('/profiles/me/publications', { method: 'POST', body: data }),
  updatePublication: (id, data) => api(`/profiles/me/publications/${id}`, { method: 'PUT', body: data }),
  deletePublication: (id) => api(`/profiles/me/publications/${id}`, { method: 'DELETE' }),

  addProject: (data) => api('/profiles/me/projects', { method: 'POST', body: data }),
  updateProject: (id, data) => api(`/profiles/me/projects/${id}`, { method: 'PUT', body: data }),
  deleteProject: (id) => api(`/profiles/me/projects/${id}`, { method: 'DELETE' }),
}

export const searchApi = {
  // params: { q, department_id, designation, page, page_size }; empty values are dropped
  search: (params) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''))
    return api(`/search?${qs}`)
  },
}

export const suggestionsApi = {
  list: (limit = 6) => api(`/suggestions?limit=${limit}`),
}

export const collaborationsApi = {
  send: (recipientId, message) =>
    api('/collaborations/requests', { method: 'POST', body: { recipient_id: recipientId, message: message || null } }),
  accept: (id) => api(`/collaborations/requests/${id}/accept`, { method: 'POST' }),
  decline: (id) => api(`/collaborations/requests/${id}/decline`, { method: 'POST' }),
  withdraw: (id) => api(`/collaborations/requests/${id}/withdraw`, { method: 'POST' }),
  sent: () => api('/collaborations/requests/sent'),
  received: () => api('/collaborations/requests/received'),
  collaborators: () => api('/collaborations'),
  relationship: (userId) => api(`/collaborations/status/${userId}`),
}

export const notificationsApi = {
  list: (page = 1, pageSize = 20) => api(`/notifications?page=${page}&page_size=${pageSize}`),
  unreadCount: () => api('/notifications/unread-count'),
  markRead: (id) => api(`/notifications/${id}/read`, { method: 'POST' }),
  markAllRead: () => api('/notifications/read-all', { method: 'POST' }),
}

// Tell the notification bell (and anything else listening) that counts may have changed
export const NOTIFICATIONS_CHANGED = 'fcn:notifications-changed'
export const announceNotificationsChanged = () => window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED))

const qs = (params) =>
  new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')).toString()

export const adminApi = {
  dashboard: () => api('/admin/dashboard'),
  users: (params) => api(`/admin/users?${qs(params)}`),
  createUser: (data) => api('/admin/users', { method: 'POST', body: data }),
  updateUser: (id, data) => api(`/admin/users/${id}`, { method: 'PATCH', body: data }),
  deactivate: (id) => api(`/admin/users/${id}/deactivate`, { method: 'POST' }),
  activate: (id) => api(`/admin/users/${id}/activate`, { method: 'POST' }),
  sendPasswordReset: (id) => api(`/admin/users/${id}/send-password-reset`, { method: 'POST' }),
  auditLogs: (params) => api(`/admin/audit-logs?${qs(params)}`),
}

export const reportsApi = {
  activity: () => api('/reports/activity'),
  department: (departmentId) => api(`/reports/department?${qs({ department_id: departmentId })}`),
}

export const accountApi = {
  changePassword: (current, next) =>
    api('/auth/change-password', { method: 'POST', body: { current_password: current, new_password: next } }),
}

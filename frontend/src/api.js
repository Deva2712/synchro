// Single place that knows how to talk to the API: one token store, one error shape.
const TOKEN_KEY = 'sentinel.token'

export const getToken = () => sessionStorage.getItem(TOKEN_KEY)
export const getRole = () => sessionStorage.getItem('sentinel.role')
export const clearSession = () => sessionStorage.clear()

async function request(path, { method = 'GET', body } = {}) {
  const response = await fetch(path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (response.status === 401) {
    clearSession()
    throw new Error('Session expired — sign in again')
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}))
    throw new Error(detail.detail || `Request failed (${response.status})`)
  }
  return response.json()
}

export async function login(email, password) {
  const data = await request('/v1/auth/login', { method: 'POST', body: { email, password } })
  sessionStorage.setItem(TOKEN_KEY, data.access_token)
  sessionStorage.setItem('sentinel.role', data.role)
  return data
}

export const listApplications = (limit = 60) => request(`/v1/applications?limit=${limit}`)
export const getApplication = (id) => request(`/v1/applications/${id}`)
export const sendFeedback = (id, label, note = '') =>
  request(`/v1/applications/${id}/feedback`, { method: 'POST', body: { label, note } })
export const getMetrics = () => request('/v1/metrics')
export const getModelInfo = () => request('/v1/model/info')
export const retrain = () => request('/v1/model/retrain', { method: 'POST' })

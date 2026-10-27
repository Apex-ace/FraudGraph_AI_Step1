export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export async function apiRequest(path, token, init = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init.body && !(init.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data.detail
    const reason = typeof detail === 'string' ? detail
      : detail?.errors ? `${detail.message} ${detail.errors.map(x => `Row ${x.row}: ${x.error}`).join(' | ')}`
      : Array.isArray(detail) ? detail.map(x => x.msg || JSON.stringify(x)).join(' | ')
      : `Request failed (${response.status})`
    throw new Error(reason)
  }
  return data
}

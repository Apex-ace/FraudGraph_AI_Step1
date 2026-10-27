// A teammate opening http://HOST_LAN_IP:5173 must not call localhost:8000,
// because localhost would point to their own laptop, not the host machine.
const requested = import.meta.env.VITE_API_URL || ''
const host = window.location.hostname
const remoteDevice = !['localhost','127.0.0.1'].includes(host)
const isLoopbackTarget = /^https?:\/\/(localhost|127\.0\.0\.1)(:|\/|$)/i.test(requested)
export const API_URL = (remoteDevice && (!requested || isLoopbackTarget)
  ? `${window.location.protocol}//${host}:8000`
  : (requested || 'http://localhost:8000')).replace(/\/$/, '')

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

import { apiRequest } from './api.js'

const STORE_KEY = 'fraudgraph_local_session_v1'

export const localAuthEnabled = (import.meta.env.VITE_AUTH_MODE || 'local').toLowerCase() !== 'supabase'

export function savedLocalSession() {
  try {
    const value = JSON.parse(window.localStorage.getItem(STORE_KEY) || 'null')
    return value?.access_token && value?.user?.id ? value : null
  } catch { return null }
}

export function clearLocalSession() {
  window.localStorage.removeItem(STORE_KEY)
}

export async function localAuthenticate(email, password, register = false) {
  const path = register ? '/api/auth/register' : '/api/auth/login'
  const session = await apiRequest(path, null, {
    method: 'POST', body: JSON.stringify({ email, password }),
  })
  window.localStorage.setItem(STORE_KEY, JSON.stringify(session))
  return session
}

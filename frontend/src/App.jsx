import { useEffect, useState } from 'react'
import { io } from 'socket.io-client'
import { API_URL, apiRequest } from './lib/api.js'
import { isSupabaseConfigured, supabase } from './lib/supabase.js'

const members = ['Anvisha Sorte', 'Chanchal Kohale', 'Kalpana Channe', 'Ayush Mishra']

function StatePill({ label, state }) {
  const tone = state === 'ok' ? 'good' : state === 'bad' ? 'bad' : 'idle'
  return <span className={`pill ${tone}`}>{label}</span>
}

export default function App() {
  const [session, setSession] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [registerMode, setRegisterMode] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [apiStatus, setApiStatus] = useState('checking')
  const [socketStatus, setSocketStatus] = useState('not connected')
  const [databaseStatus, setDatabaseStatus] = useState('not checked')
  const [events, setEvents] = useState([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    if (!supabase) {
      setAuthLoading(false)
      return
    }
    supabase.auth.getSession().then(({ data }) => {
      if (active) { setSession(data.session); setAuthLoading(false) }
    }).catch(() => { if (active) setAuthLoading(false) })
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (active) setSession(nextSession)
    })
    return () => { active = false; subscription.unsubscribe() }
  }, [])

  useEffect(() => {
    apiRequest('/api/health')
      .then(() => setApiStatus('online'))
      .catch(() => setApiStatus('offline'))
  }, [])

  const token = session?.access_token
  useEffect(() => {
    if (!token) { setSocketStatus('not connected'); return }
    const socket = io(API_URL, {
      autoConnect: true,
      auth: { token },
      transports: ['websocket', 'polling'],
    })
    socket.on('connect', () => setSocketStatus('connected'))
    socket.on('disconnect', () => setSocketStatus('disconnected'))
    socket.on('connect_error', (error) => setSocketStatus(`error: ${error.message}`))
    socket.on('fraud_alert_demo', (event) => setEvents((previous) => [event, ...previous].slice(0, 8)))
    return () => socket.disconnect()
  }, [token])

  async function handleAuth(event) {
    event.preventDefault()
    if (!supabase) return
    setBusy(true)
    setMessage('')
    try {
      const response = registerMode
        ? await supabase.auth.signUp({ email, password })
        : await supabase.auth.signInWithPassword({ email, password })
      if (response.error) throw response.error
      setMessage(registerMode
        ? (response.data.session ? 'Account created and signed in.' : 'Account created. Confirm your email if required, then sign in.')
        : 'Signed in successfully.')
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  async function testDatabase() {
    setDatabaseStatus('checking')
    try {
      const result = await apiRequest('/api/health/database', token)
      setDatabaseStatus(result.status)
    } catch (error) {
      setDatabaseStatus(error.message)
    }
  }

  async function triggerDemo() {
    setBusy(true)
    setMessage('')
    try {
      await apiRequest('/api/demo/notify', token, {
        method: 'POST',
        body: JSON.stringify({ message: 'Test alert: circular A → B → C → A transfers (synthetic data).' }),
      })
      setMessage('Test event sent. Check the live notifications section.')
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  async function logout() {
    const { error } = await supabase.auth.signOut()
    if (error) setMessage(error.message)
    else { setEvents([]); setDatabaseStatus('not checked'); setMessage('Signed out.') }
  }

  return (
    <div className="site">
      <header className="topbar">
        <div className="brand"><div className="logo-mark">FG</div><div><strong>FraudGraph <span>AI</span></strong><small>TEAM INNOVA · TECHVERSE 2.0</small></div></div>
        <div className="header-right"><StatePill label={`API: ${apiStatus}`} state={apiStatus === 'online' ? 'ok' : 'bad'} /><span className="top-tag">FT-PS-02</span></div>
      </header>
      <main className="container">
        <section className="hero">
          <div className="eyebrow">STEP 01 / PROJECT FOUNDATION</div>
          <h1>Build a safer <span>financial network.</span></h1>
          <p>React + FastAPI + Supabase PostgreSQL + Socket.IO. This starter verifies our architecture before transaction ingestion and fraud detection.</p>
          <div className="hero-tags"><span>React + Vite</span><span>FastAPI</span><span>Supabase</span><span>Socket.IO</span></div>
        </section>
        <div className="layout">
          <section className="panel auth-panel">
            <div className="section-tag">01 · AUTHENTICATION</div>
            <h2>Supabase authentication</h2>
            {!isSupabaseConfigured ? (
              <div className="notice warn"><strong>Configure Supabase first.</strong><p>Fill in <code>frontend/.env</code> using the supplied <code>.env.example</code>, then restart Vite.</p></div>
            ) : authLoading ? <p className="muted">Checking existing session...</p> : session ? (
              <div className="signedin">
                <div className="avatar">{(session.user?.email || 'U').slice(0, 1).toUpperCase()}</div>
                <p className="muted">Authenticated as</p><h3>{session.user?.email || session.user?.id}</h3>
                <p className="small muted">Supabase Auth user ID: <code>{session.user?.id}</code></p>
                <button className="secondary" type="button" onClick={logout}>Sign out</button>
              </div>
            ) : (
              <form onSubmit={handleAuth} className="auth-form">
                <label>Email<input required type="email" autoComplete="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
                <label>Password<input required minLength={6} type="password" autoComplete={registerMode ? 'new-password' : 'current-password'} placeholder="At least 6 characters" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
                <button type="submit" disabled={busy}>{busy ? 'Working...' : registerMode ? 'Create account' : 'Sign in'}</button>
                <button className="text-button" type="button" onClick={() => setRegisterMode(!registerMode)}>{registerMode ? 'Already have an account? Sign in' : 'New here? Create an account'}</button>
              </form>
            )}
            {message && <div className="notice">{message}</div>}
          </section>
          <section className="panel status-panel">
            <div className="section-tag">02 · LIVE INTEGRATION</div>
            <h2>Service connectivity</h2>
            <div className="status-row"><div><strong>FastAPI backend</strong><small>GET /api/health</small></div><StatePill label={apiStatus} state={apiStatus === 'online' ? 'ok' : 'bad'} /></div>
            <div className="status-row"><div><strong>Socket.IO</strong><small>Authenticated personal channel</small></div><StatePill label={socketStatus} state={socketStatus === 'connected' ? 'ok' : socketStatus.startsWith('error') ? 'bad' : 'idle'} /></div>
            <div className="status-row"><div><strong>Supabase PostgreSQL</strong><small>Authenticated SELECT 1 check</small></div><StatePill label={databaseStatus} state={databaseStatus === 'connected' ? 'ok' : databaseStatus === 'not checked' ? 'idle' : 'bad'} /></div>
            <div className="actions"><button onClick={testDatabase} disabled={!session}>Test database</button><button className="outline" onClick={triggerDemo} disabled={!session || busy || socketStatus !== 'connected'}>Send test notification</button></div>
            {!session && <p className="tiny muted">Sign in to test protected database and Socket.IO connectivity.</p>}
          </section>
        </div>
        <section className="panel notifications">
          <div><div className="section-tag">03 · SOCKET.IO</div><h2>Live notifications <span className="count">{events.length}</span></h2><p className="muted small">Step 1 sends demo events only. Fraud detection and persistent alerts are implemented in later steps.</p></div>
          {events.length === 0 ? <div className="empty">No demo events received yet. Sign in, connect Socket.IO and send a test notification.</div> : events.map((event) => (
            <div className="event" key={event.id}><span className="event-dot"/><div><strong>{event.title}</strong><p>{event.message}</p><small>{new Date(event.created_at).toLocaleString()}</small></div><span className="event-tag">DEMO</span></div>
          ))}
        </section>
        <footer>Team Innova <span>·</span> {members.join(' · ')} <span>·</span> Prototype Step 1</footer>
      </main>
    </div>
  )
}

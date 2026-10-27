import { useCallback, useEffect, useMemo, useState } from 'react'
import { io } from 'socket.io-client'
import {
  Activity, Bell, CheckCircle2, ChevronRight, CircleHelp, Database, FileSpreadsheet,
  Gauge, GitBranch, LayoutDashboard, LogOut, Network, Pause, Play, Radio,
  RotateCw, Search, Settings2, Shield, ShieldAlert, SquareActivity, Trash2,
  Upload, Users, Wallet, X
} from 'lucide-react'
import { API_URL, apiRequest } from './lib/api.js'
import { isSupabaseConfigured, supabase } from './lib/supabase.js'
import FraudNetwork from './components/FraudNetwork.jsx'
import TransactionWorkspace from './components/TransactionWorkspace.jsx'

const team = 'Team Innova · TECHVERSE 2.0'
const money = (x) => new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(x || 0)
const nav = [
  {name:'Overview',icon:LayoutDashboard,group:'MONITORING'},
  {name:'Network Explorer',icon:Network},
  {name:'Fraud Alerts',icon:ShieldAlert},
  {name:'Transactions',icon:FileSpreadsheet,group:'DATA MANAGEMENT'},
  {name:'Accounts',icon:Users},
  {name:'CSV Import',icon:Upload},
  {name:'Live Simulator',icon:Activity,group:'SYSTEM'},
  {name:'Connectivity',icon:Settings2},
]
const emptyGraph = {nodes:[],edges:[],transactions:[],scenarios:[],total_transactions:0,window_count:0,simulated_count:0}
const emptyOverview = {accounts:0,transactions:0,completed_transactions:0,import_batches:0}
const fmt = (date) => date ? new Date(date).toLocaleString() : '—'

function Hint({text}) { return <span className="help-dot" title={text} tabIndex={0} aria-label={text}><CircleHelp size={14}/><span className="help-tooltip">{text}</span></span> }
function Status({good,children}) {return <span className={`connection-status ${good?'connected':'disconnected'}`}><span className="status-light"/>{children}</span>}
function Kpi({title,value,icon:Icon,help,note}) {return <div className="kpi"><div className="kpi-line"><span>{title}<Hint text={help}/></span><Icon size={17}/></div><strong>{value}</strong><small>{note}</small></div>}
function SectionHeader({title,description,action}) {return <div className="module-heading"><div><h2>{title}</h2><p>{description}</p></div>{action}</div>}

export default function App() {
  const [session,setSession]=useState(null),[authReady,setAuthReady]=useState(false)
  const [register,setRegister]=useState(false),[email,setEmail]=useState(''),[password,setPassword]=useState('')
  const [page,setPage]=useState('Overview'),[notice,setNotice]=useState(''),[authBusy,setAuthBusy]=useState(false)
  const [health,setHealth]=useState('checking'),[socketStatus,setSocketStatus]=useState('disconnected'),[dbStatus,setDbStatus]=useState('not tested')
  const [graph,setGraph]=useState(emptyGraph),[overview,setOverview]=useState(emptyOverview)
  const [alerts,setAlerts]=useState([]),[selectedAlert,setSelectedAlert]=useState(null)
  const [sim,setSim]=useState({running:false,ticks:0,max_ticks:120,interval_seconds:3,error:null}),[interval,setIntervalSeconds]=useState(3)
  const [revision,setRevision]=useState(0),[busy,setBusy]=useState(false),[liveEvents,setLiveEvents]=useState([])
  const [graphMode,setGraphMode]=useState('all'),[search,setSearch]=useState('')
  const [modelStatus,setModelStatus]=useState(null)
  const token = session?.access_token

  useEffect(()=>{
    let active = true
    if(!supabase){setAuthReady(true);return}
    supabase.auth.getSession().then(({data})=>{if(active){setSession(data.session);setAuthReady(true)}}).catch(()=>{if(active)setAuthReady(true)})
    const {data:{subscription}}=supabase.auth.onAuthStateChange((_event,value)=>{if(active)setSession(value)})
    return ()=>{active=false;subscription.unsubscribe()}
  },[])

  useEffect(()=>{apiRequest('/api/health').then(()=>setHealth('online')).catch(()=>setHealth('offline'))},[])
  const refresh=useCallback(async()=>{
    if(!token)return
    try {
      const [g,o,s,a]=await Promise.all([
        apiRequest('/api/monitor/graph?limit=400',token),
        apiRequest('/api/overview',token),
        apiRequest('/api/simulation/status',token),
        apiRequest('/api/detection/alerts?limit=100',token)
      ])
      setGraph(g);setOverview(o);setSim(s);setAlerts(a.items || [])
    } catch(e){setNotice(e.message)}
  },[token])
  useEffect(()=>{refresh()},[refresh,revision])
  useEffect(()=>{if(token){apiRequest('/api/detection/status',token).then(setModelStatus).catch(()=>setModelStatus(null))}},[token])
  useEffect(()=>{
    if(!token)return
    const timer=window.setInterval(()=>refresh(),20000)
    return()=>window.clearInterval(timer)
  },[token,refresh])
  useEffect(()=>{
    if(!token){setSocketStatus('disconnected');setLiveEvents([]);return}
    const socket=io(API_URL,{auth:{token},transports:['websocket','polling']})
    socket.on('connect',()=>{setSocketStatus('connected');setRevision(v=>v+1)})
    socket.on('disconnect',()=>setSocketStatus('disconnected'))
    socket.on('connect_error',e=>setSocketStatus(`error: ${e.message}`))
    socket.on('fraud_alert_detected',event=>{
      setNotice(`ML alert · ${event.name}: risk ${event.risk_score}/100. Review evidence under Fraud Alerts.`)
      setRevision(v=>v+1)
    })
    socket.on('simulation_transactions',event=>{
      setLiveEvents(prev=>[...event.transactions,...prev].slice(0,30))
      setRevision(v=>v+1)
    })
    socket.on('simulation_status',()=>setRevision(v=>v+1))
    socket.on('simulation_reset',()=>{setLiveEvents([]);setRevision(v=>v+1)})
    socket.on('fraud_alert_demo',event=>setNotice(`Demo notification: ${event.message}`))
    return()=>socket.disconnect()
  },[token])

  const dataSummary=useMemo(()=>({
    detectedAlerts:alerts.length,
    totalValue:(graph.transactions || []).reduce((sum,x)=>sum+Number(x.amount),0)
  }),[graph,alerts])

  async function submitAuth(e){
    e.preventDefault();setAuthBusy(true);setNotice('')
    try{const result=register?await supabase.auth.signUp({email,password}):await supabase.auth.signInWithPassword({email,password});if(result.error)throw result.error;if(register&&!result.data.session)setNotice('Check your inbox to confirm your account, then sign in.')}
    catch(e){setNotice(e.message)}finally{setAuthBusy(false)}
  }
  async function signOut(){const {error}=await supabase.auth.signOut();if(error)setNotice(error.message);else{setPage('Overview');setGraph(emptyGraph);setOverview(emptyOverview);setAlerts([]);setSelectedAlert(null)}}
  async function start(){setBusy(true);setNotice('');try{const s=await apiRequest('/api/simulation/start',token,{method:'POST',body:JSON.stringify({interval_seconds:Number(interval)})});setSim(s);setNotice('Live simulation started. Generated transactions will be saved to Supabase.')}
    catch(e){setNotice(e.message)}finally{setBusy(false);setRevision(v=>v+1)}}
  async function stop(){setBusy(true);try{setSim(await apiRequest('/api/simulation/stop',token,{method:'POST'}))}catch(e){setNotice(e.message)}finally{setBusy(false);setRevision(v=>v+1)}}
  async function reset(){if(!window.confirm('Remove ONLY generated FGSIM_ demo transactions from your account? Imported and manually entered transactions will remain.'))return;setBusy(true)
    try{const res=await apiRequest('/api/simulation/reset',token,{method:'POST',body:JSON.stringify({confirm:'RESET_SIMULATION'})});setNotice(`${res.deleted} generated transactions deleted.`);setLiveEvents([])}
    catch(e){setNotice(e.message)}finally{setBusy(false);setRevision(v=>v+1)}}
  async function testDb(){setDbStatus('checking');try{const result=await apiRequest('/api/health/database',token);setDbStatus(result.status)}catch(e){setDbStatus(`error: ${e.message}`)}}
  async function analyze(){
    setBusy(true);setNotice('')
    try {
      const res=await apiRequest('/api/detection/analyze',token,{method:'POST'})
      setNotice(`Independent model scan finished: ${res.new_alerts} new ML-backed alerts.`)
      setRevision(v=>v+1)
    }catch(e){setNotice(e.message)}finally{setBusy(false)}
  }
  async function notify(){try{await apiRequest('/api/demo/notify',token,{method:'POST',body:JSON.stringify({message:'Test delivery to your authenticated Socket.IO room (synthetic demo only).'})});setNotice('Sent test notification.')}
    catch(e){setNotice(e.message)}}

  function simulatorControls(){return <div className="sim-controls"><label>Transfer interval <Hint text="Only simulated transactions. Each tick writes a real record to your own Supabase PostgreSQL database."/><select value={interval} disabled={sim.running||busy} onChange={e=>setIntervalSeconds(Number(e.target.value))}>{[2,3,5,10].map(n=><option key={n} value={n}>{n} seconds</option>)}</select></label>
    {sim.running?<button className="button-danger" onClick={stop} disabled={busy}><Pause size={16}/> Stop Simulation</button>:<button onClick={start} disabled={busy}><Play size={16}/> Start Simulation</button>}
    <button className="button-light" onClick={reset} disabled={sim.running||busy} title="Delete generated FGSIM_ transactions, never imported CSV data"><Trash2 size={15}/> Reset Demo Data</button>
  </div>}
  function networkCard(){return <section className="module network-module"><div className="module-heading graph-heading"><div><h2>Transaction network <Hint text="Nodes represent accounts. Red connections are linked to actual ML-backed anomaly alerts, not predefined simulator labels. Alerts do not establish fraud."/></h2><p>Account relationships derived from the latest {graph.window_count} stored transactions.</p></div><div className="graph-filters"><label className="search-field"><Search size={15}/><input placeholder="Find account ID" value={search} onChange={e=>setSearch(e.target.value)} aria-label="Find account ID"/></label><select value={graphMode} onChange={e=>setGraphMode(e.target.value)} aria-label="Graph edge filter"><option value="all">All connections</option><option value="scenarios">ML-flagged paths</option></select></div></div>
    <FraudNetwork graph={graph} mode={graphMode} search={search}/>
    <div className="graph-legend"><span><b style={{background:'#59768b'}}/> Bank</span><span><b style={{background:'#16998a'}}/> Customer</span><span><b style={{background:'#0c88b7'}}/> Wallet</span><span><b style={{background:'#84ad40'}}/> Merchant</span><span><b style={{background:'#d53b42'}}/> ML-flagged path</span><small>Hover nodes or edges for details · Drag to pan · Scroll to zoom</small></div>
  </section>}
  function activityCard(){return <section className="module activity-panel"><div className="module-heading"><div><h2>Recent transaction activity</h2><p>Newest ledger entries, not placeholder animations.</p></div><button className="icon-button" title="Refresh latest transactions" onClick={()=>setRevision(v=>v+1)}><RotateCw size={16}/></button></div>
    <div className="activity-list">{(graph.transactions||[]).slice(0,9).map(t=><div className="activity-item" key={t.id}><span className={`activity-mark ${t.scenario?'red':''}`}><GitBranch size={14}/></span><div><strong>{t.source} <ChevronRight size={12}/> {t.target}</strong><small>{fmt(t.at)} · {t.scenario?`ML-detected ${t.scenario} pattern`:'Standard flow'}</small></div><b>{money(t.amount)}</b></div>)}{!graph.transactions?.length&&<p className="empty-message">No activity yet. Start the simulator to create data.</p>}</div>
  </section>}

  if(!authReady)return <div className="auth-screen">Loading authentication…</div>
  if(!session)return <div className="auth-screen"><div className="login-card"><div className="login-brand"><Shield size={26}/><div><strong>FraudGraph AI</strong><small>Financial network intelligence · {team}</small></div></div><h1>{register?'Create investigator account':'Sign in to your workspace'}</h1><p>Secure, owner-scoped synthetic transaction analysis.</p>{!isSupabaseConfigured?<div className="feedback">Add your Supabase URL and publishable key to frontend/.env.</div>:<form onSubmit={submitAuth} className="login-form"><label>Work email<input type="email" value={email} required onChange={e=>setEmail(e.target.value)} placeholder="name@example.com"/></label><label>Password<input type="password" value={password} required minLength="6" onChange={e=>setPassword(e.target.value)}/></label><button disabled={authBusy}>{authBusy?'Please wait…':register?'Create account':'Sign in'}</button></form>}<button className="text-button" onClick={()=>setRegister(!register)}>{register?'Return to sign in':'Need an account? Register'}</button>{notice&&<div className="feedback">{notice}</div>}<div className="login-foot">DEMONSTRATION PLATFORM · NO REAL BANKING TRANSACTIONS</div></div></div>

  return <div className="app-shell">
    <aside className="sidebar"><div className="sidebar-brand"><span className="brand-symbol"><Shield size={23}/></span><div><strong>FraudGraph AI</strong><small>RISK INTELLIGENCE SYSTEM</small></div></div>
      <div className="sidebar-workspace"><span>WORKSPACE</span><b>Team Innova</b><small>Financial fraud simulation</small></div>
      <nav aria-label="Main navigation">{nav.map(item=><div key={item.name}>{item.group&&<div className="nav-group">{item.group}</div>}<button className={`nav-entry ${page===item.name?'active':''}`} onClick={()=>setPage(item.name)}><item.icon size={18}/>{item.name}{item.name==='Live Simulator'&&sim.running&&<span className="live-mini"/>}</button></div>)}</nav>
      <div className="sidebar-bottom"><span className="demo-flag"><Radio size={15}/> SYNTHETIC DATA ONLY</span><small>FT-PS-02 · TECHVERSE 2.0</small></div>
    </aside>
    <div className="main-column"><header className="app-header"><div className="breadcrumb">Fraud Monitoring <ChevronRight size={14}/> <strong>{page}</strong></div><div className="header-tools"><Status good={health==='online'}>API {health}</Status><Status good={socketStatus==='connected'}>Socket {socketStatus==='connected'?'connected':'offline'}</Status><span className="header-divider"/><span className="operator"><span className="user-dot">{(session.user?.email||'U')[0].toUpperCase()}</span><span>{session.user?.email}</span></span><button className="icon-button" onClick={signOut} title="Sign out of FraudGraph" aria-label="Sign out"><LogOut size={17}/></button></div></header>
      <main className="main-content">
        <div className="page-heading"><div><span className="eyebrow">FINTECH / DIGITAL TRUST</span><h1>{page}</h1><p>{page==='Overview'?'Live financial transaction monitoring and graph-based exploration.':'Synthetic transaction analysis and operations workspace.'}</p></div><div className="page-heading-side"><span className={`live-marker ${sim.running?'running':''}`}><Radio size={15}/>{sim.running?'Simulation running':'Simulation stopped'}</span>{page!=='Live Simulator'&&<button className="button-light" onClick={()=>setPage('Live Simulator')}><Gauge size={16}/> Open simulator</button>}</div></div>
        {notice&&<div className="feedback" role="status">{notice}<button onClick={()=>setNotice('')} aria-label="Close message"><X size={16}/></button></div>}
        {(page==='Overview'||page==='Network Explorer'||page==='Live Simulator')&&<div className="kpi-grid">
          <Kpi title="Transactions" value={overview.transactions.toLocaleString('en-IN')} icon={FileSpreadsheet} note="Persisted ledger records" help="Total transactions saved in your Supabase PostgreSQL ledger, including manually uploaded and simulated data."/>
          <Kpi title="Accounts" value={overview.accounts.toLocaleString('en-IN')} icon={Wallet} note="Linked account entities" help="Distinct account records for your signed-in user."/>
          <Kpi title="ML-backed alerts" value={dataSummary.detectedAlerts} icon={ShieldAlert} note="Model-confirmed anomalies" help="Count of evidence-linked graph patterns independently confirmed by the trained Isolation Forest model. These are risk indicators, not proof of fraud."/>
          <Kpi title="Generated transactions" value={graph.simulated_count.toLocaleString('en-IN')} icon={SquareActivity} note={`Current run: ${sim.ticks}/${sim.max_ticks} ticks`} help="Rows generated by the opt-in simulator; these are real database rows, but represent fictitious money movements."/>
        </div>}
        {page==='Overview'&&<><div className="live-strip"><span className={`live-indicator ${sim.running?'on':''}`}/><div><strong>{sim.running?'Live synthetic stream active':'Synthetic stream paused'}</strong><small>{sim.running?`A transaction is saved every ${sim.interval_seconds}s and pushed through Socket.IO.`:'Click Start Simulation to populate the graph and generate live data.'}</small></div>{sim.running?<button className="button-danger" onClick={stop} disabled={busy}><Pause size={15}/> Stop</button>:<button onClick={start} disabled={busy}><Play size={15}/> Start Simulation</button>}</div>
          {networkCard()}<div className="two-cols">{activityCard()}<section className="module"><SectionHeader title="Detected anomalies" description="Actual pattern evidence with trained ML anomaly scores; synthetic-data validation." action={<button className="button-light" onClick={()=>setPage('Fraud Alerts')}>View all</button>}/>{graph.scenarios?.length?graph.scenarios.slice(0,5).map(e=><div className="scenario-row" key={e.id}><span className={`severity ${e.severity}`}>{e.severity}</span><div><strong>{e.name}</strong><small>{e.description} · Risk {e.risk_score}/100 · ML index {e.anomaly_index}</small></div><small>{fmt(e.at)}</small></div>):<p className="empty-message">No ML-backed alerts yet. Run the simulator or analyze imported transactions.</p>}</section></div>
        </>}
        {page==='Network Explorer'&&networkCard()}
        {page==='Live Simulator'&&<><section className="module"><SectionHeader title="Synthetic transaction generator" description="Controlled backend simulator using PostgreSQL persistence and private Socket.IO events." action={<Status good={sim.running}>{sim.running?'RUNNING':'STOPPED'}</Status>}/><p className="callout">All generated account identifiers and amounts are fictitious. This system does not transfer money or connect to banks. A run automatically stops after {sim.max_ticks} ticks; each account has a 1,200-row safety cap.</p>{simulatorControls()}{sim.error&&<div className="feedback error">Simulator error: {sim.error}</div>}<div className="sim-details"><div><strong>{sim.ticks}</strong><small>Ticks generated in current run</small></div><div><strong>{graph.simulated_count}</strong><small>Rows stored in Supabase</small></div><div><strong>{liveEvents.length}</strong><small>Latest Socket.IO messages shown</small></div></div></section><div className="two-cols">{activityCard()}<section className="module"><SectionHeader title="Live stream diagnostics" description="Verify backend and event delivery."/><div className="status-line"><span>FastAPI</span><Status good={health==='online'}>{health}</Status></div><div className="status-line"><span>Socket.IO authenticated</span><Status good={socketStatus==='connected'}>{socketStatus==='connected'?'Connected':'Disconnected'}</Status></div><div className="status-line"><span>Database</span><span>{dbStatus}</span></div><button className="button-light" onClick={testDb}><Database size={15}/> Test database</button></section></div></>}
        {page==='Fraud Alerts'&&<section className="module"><SectionHeader title="Fraud investigation alerts" description="Evidence-backed graph patterns independently scored by Isolation Forest." action={<button onClick={analyze} disabled={busy}><ShieldAlert size={15}/> {busy?'Analyzing…':'Analyze transactions'}</button>}/><p className="callout"><ShieldAlert size={16}/> The detection engine uses NetworkX + trained Isolation Forest. Risk scores are uncalibrated demo indices, not probabilities or confirmed fraud. {modelStatus?.version ? `Model: ${modelStatus.version}` : ''}</p><div className="table-scroll"><table className="data-table"><thead><tr><th>Alert</th><th>Pattern</th><th>Accounts</th><th>Risk</th><th>ML index</th><th>Evidence transfers</th><th>Detected</th><th>Details</th></tr></thead><tbody>{alerts.map(e=><tr key={e.id}><td className="mono">{e.id.slice(0,8)}</td><td>{e.name}</td><td className="mono">{e.accounts.join(', ')}</td><td><strong title="A relative demo risk index, not a fraud probability">{e.risk_score}/100</strong></td><td title="Isolation Forest anomaly index; higher means less like the synthetic reference">{e.anomaly_index}</td><td>{e.transaction_ids.length} transactions</td><td>{fmt(e.at)}</td><td><button className="button-light" onClick={()=>setSelectedAlert(e)}>Evidence</button></td></tr>)}{!alerts.length&&<tr><td colSpan="8" className="table-empty">No ML-confirmed alerts. Press Analyze transactions or run a sample simulation.</td></tr>}</tbody></table></div>
        {selectedAlert&&<div className="evidence-panel"><div className="module-heading"><div><h2>Evidence · {selectedAlert.name}</h2><p>Detection model: {selectedAlert.model_version} · Risk {selectedAlert.risk_score}/100 · ML anomaly index {selectedAlert.anomaly_index}</p></div><button className="button-light" onClick={()=>setSelectedAlert(null)}>Close evidence</button></div><p className="muted">This is a suspicious behavioral pattern, not a confirmed fraud finding. Feature values summarize the linked transfers; they are not model attribution explanations.</p><div className="table-scroll"><table className="data-table"><thead><tr><th>Transaction</th><th>Sender</th><th>Receiver</th><th>Amount</th><th>Timestamp</th></tr></thead><tbody>{(selectedAlert.evidence?.transfers||[]).map(t=><tr key={t.id}><td className="mono">{t.id}</td><td>{t.source}</td><td>{t.target}</td><td>{money(t.amount)}</td><td>{fmt(t.at)}</td></tr>)}</tbody></table></div><div className="evidence-features"><strong>Model input features</strong><div className="feature-grid">{Object.entries(selectedAlert.evidence?.feature_summary||{}).map(([key,value])=><div key={key}><small>{key.replaceAll('_',' ')}</small><strong>{value}</strong></div>)}</div></div></div>}</section>}
        {['Transactions','Accounts','CSV Import'].includes(page)&&<div className="module"><TransactionWorkspace token={token} view={{Transactions:'transactions',Accounts:'accounts','CSV Import':'imports'}[page]} onChanged={()=>setRevision(v=>v+1)} refreshKey={revision}/></div>}
        {page==='Connectivity'&&<section className="module"><SectionHeader title="Service connectivity" description="Authentication, database and private real-time channel status."/><div className="status-line"><span>FastAPI backend</span><Status good={health==='online'}>{health}</Status></div><div className="status-line"><span>Socket.IO personal room</span><Status good={socketStatus==='connected'}>{socketStatus}</Status></div><div className="status-line"><span>Supabase PostgreSQL</span><span>{dbStatus}</span></div><div className="button-row"><button onClick={testDb}><Database size={15}/> Test database</button><button className="button-light" onClick={notify} disabled={socketStatus!=='connected'}><Bell size={15}/> Test notification</button></div><p className="muted">Authenticated as {session.user?.email}. No database passwords or tokens are displayed. ML status: {modelStatus?.ready ? modelStatus.version : 'not loaded'}.</p></section>}
      <footer>FraudGraph AI · Team Innova · Anvisha Sorte · Chanchal Kohale · Kalpana Channe · Ayush Mishra <span>· Simulation, not live banking data</span></footer>
      </main>
    </div>
  </div>
}

import { Activity, BarChart3, BrainCircuit, ShieldAlert, Users } from 'lucide-react'

const number = (value) => Number(value || 0).toLocaleString('en-IN')

function DataBar({ label, value, max, subtitle }) {
  const width = max > 0 ? Math.max(0, Math.min(100, 100 * value / max)) : 0
  return <div className="intel-bar-row">
    <div className="intel-bar-label"><strong>{label}</strong><span>{number(value)} {subtitle || ''}</span></div>
    <div className="intel-bar-track"><span style={{ width: `${width}%` }} /></div>
  </div>
}

export default function IntelligencePanel({ data, loading, error, onRefresh }) {
  if (!data) return <section className="module"><div className="module-heading"><div><h2>AI fraud intelligence</h2><p>Computed from your persisted investigation records</p></div><button className="button-light" onClick={onRefresh}>Retry</button></div><p className="muted">{error || (loading ? 'Calculating analytics…' : 'Open this page to load analytics.')}</p></section>
  const maxPattern = Math.max(1, ...data.patterns.map(x => x.count))
  const maxActivity = Math.max(1, ...data.activity.map(x => x.completed))
  return <div className="intelligence-stack">
    <section className="module"><div className="module-heading"><div><h2>Fraud intelligence dashboard</h2><p>Observed transaction and anomaly evidence from your local SQLite records</p></div><button className="button-light" onClick={onRefresh} disabled={loading}><Activity size={15}/>{loading ? 'Refreshing…' : 'Refresh statistics'}</button></div>
      <div className="intel-cards">
        {[
          {title:'Total transactions',value:data.total_transactions,icon:BarChart3},
          {title:'ML-backed alerts',value:data.total_alerts,icon:ShieldAlert},
          {title:'Accounts appearing in alerts',value:data.flagged_accounts,icon:Users},
          {title:'Average alert risk index',value:`${data.average_risk}/100`,icon:BrainCircuit},
        ].map(item => <div className="intel-kpi" key={item.title}><item.icon size={19}/><small>{item.title}</small><strong>{typeof item.value === 'number' ? number(item.value) : item.value}</strong></div>)}
      </div>
    </section>
    <div className="intel-two-cols">
      <section className="module"><h2>Detected behavior categories</h2><p className="muted">Number of saved ML-confirmed graph-pattern alerts.</p><div className="intel-bars">{data.patterns.map(p => <DataBar key={p.key} label={p.name} value={p.count} max={maxPattern}/>)}</div></section>
      <section className="module"><h2>Alert risk distribution</h2><p className="muted">Risk bands are demonstration indexes, not fraud probabilities.</p><div className="intel-bars"><DataBar label="High (85–100)" value={data.risk_bands.high} max={data.total_alerts}/><DataBar label="Elevated (75–84)" value={data.risk_bands.elevated} max={data.total_alerts}/><DataBar label="Moderate (below 75)" value={data.risk_bands.moderate} max={data.total_alerts}/></div><div className="intel-foot">High-severity alerts (≥80): {number(data.severity.high)} · Mean ML anomaly index: {data.average_anomaly_index}</div></section>
    </div>
    <section className="module"><h2>Completed transaction activity</h2><p className="muted">Seven-day window ending {data.sample_window.end_date || 'at the latest transaction'}, based on the latest {number(data.sample_window.max_rows)} recorded entries or fewer.</p>
      <div className="intel-activity" role="img" aria-label="Seven-day completed transaction counts">{data.activity.length ? data.activity.map(day=><div className="intel-day" key={day.day}><b>{day.completed}</b><span className="intel-activity-track"><i style={{height:`${Math.max(2,100*day.completed/maxActivity)}%`}} /></span><small>{day.day.slice(5)}</small></div>) : <p>No transactions have been recorded yet.</p>}</div>
      <p className="muted">{data.data_note} The model uses {data.model_version}.</p>
    </section>
  </div>
}

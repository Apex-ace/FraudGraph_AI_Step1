import { Download, Printer, X } from 'lucide-react'
const fmt = date => date ? new Date(date).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : '—'
const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(value) || 0)
export default function InvestigationReport({ alert, onClose }) {
  if (!alert) return null
  const transactions = alert.evidence?.transfers || []
  const exportCsv = () => {
    const clean = s => `"${String(s ?? '').replace(/"/g, '""')}"`
    const csv = [['Transaction ID','Sender','Receiver','Amount INR','Timestamp UTC'],...transactions.map(tx => [tx.id,tx.source,tx.target,tx.amount,tx.at])].map(row => row.map(clean).join(',')).join('\r\n')
    const url = URL.createObjectURL(new Blob([csv], {type:'text/csv;charset=utf-8'}))
    const a = document.createElement('a'); a.href = url; a.download = `FraudGraph_Evidence_${alert.id.slice(0,8)}.csv`; a.click(); URL.revokeObjectURL(url)
  }
  return <div className="report-overlay" role="dialog" aria-modal="true" aria-label="Fraud investigation report">
    <div className="report-shell">
      <div className="report-controls"><strong>Investigation report preview</strong><div><button className="button-light" onClick={exportCsv}><Download size={15}/> Export evidence CSV</button><button onClick={() => window.print()}><Printer size={15}/> Print / Save as PDF</button><button className="button-light" onClick={onClose} aria-label="Close report"><X size={15}/></button></div></div>
      <article className="report-paper" id="fraudgraph-print-report">
        <header><div><h1>FraudGraph AI</h1><span>Team Innova · TECHVERSE 2.0 · Investigation record</span></div><div className="report-ref">CASE {alert.id.slice(0,8).toUpperCase()}<small>{fmt(alert.at)} IST</small></div></header>
        <h2>{alert.name}</h2><p>{alert.summary}</p>
        <div className="report-stat-row"><div><span>Risk index</span><strong>{alert.risk_score} / 100</strong></div><div><span>ML anomaly index</span><strong>{alert.anomaly_index}</strong></div><div><span>Severity</span><strong>{alert.severity}</strong></div><div><span>Model version</span><strong>{alert.model_version}</strong></div></div>
        <h3>Accounts involved</h3><p className="report-mono">{alert.accounts.join(' · ')}</p>
        <h3>Transaction evidence</h3><table><thead><tr><th>Reference</th><th>Source</th><th>Destination</th><th>Amount</th><th>Timestamp</th></tr></thead><tbody>{transactions.map(tx=><tr key={tx.id}><td>{tx.id}</td><td>{tx.source}</td><td>{tx.target}</td><td>{money(tx.amount)}</td><td>{fmt(tx.at)}</td></tr>)}</tbody></table>
        <h3>Model input features</h3><div className="report-features">{Object.entries(alert.evidence?.feature_summary || {}).map(([key,value]) => <div key={key}><span>{key.replaceAll('_',' ')}</span><strong>{value}</strong></div>)}</div>
        <p className="report-disclaimer"><strong>Investigation disclaimer:</strong> This report documents potential anomalies in synthetic financial activity. Anomalies are not evidence of criminal intent. Scores are uncalibrated demonstration indexes and the features shown are model inputs, not causal attributions.</p>
        <footer>Prepared by FraudGraph AI · Team Innova · TECHVERSE 2.0</footer>
      </article>
    </div>
  </div>
}

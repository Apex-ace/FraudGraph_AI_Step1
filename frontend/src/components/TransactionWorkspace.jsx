import { useCallback, useEffect, useState } from 'react'
import { apiRequest } from '../lib/api.js'
import { Upload, PlusCircle, Download } from 'lucide-react'

const money = (amount) => new Intl.NumberFormat('en-IN', {style:'currency',currency:'INR',maximumFractionDigits:2}).format(amount || 0)

export default function TransactionWorkspace({ token, view, onChanged, refreshKey }) {
  const [accounts, setAccounts] = useState([])
  const [items, setItems] = useState([])
  const [imports, setImports] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [status, setStatus] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [account, setAccount] = useState({account_code:'',label:''})
  const [tx, setTx] = useState({transaction_id:'',sender_account:'',receiver_account:'',amount:'',currency:'INR',occurred_at:'',status:'completed'})
  const [file, setFile] = useState(null)
  const reload = useCallback(async () => {
    if (!token) return
    try {
      const [a, t, i] = await Promise.all([
        apiRequest('/api/accounts',token),
        apiRequest(`/api/transactions?limit=20&offset=${page*20}${status ? `&status=${status}` : ''}`,token),
        apiRequest('/api/imports',token)
      ])
      setAccounts(a); setItems(t.items); setTotal(t.total); setImports(i)
    } catch (e) { setMessage(e.message) }
  }, [token,page,status])
  useEffect(() => { reload() }, [reload,refreshKey])
  async function submitAccount(e) {
    e.preventDefault(); setBusy(true); setMessage('')
    try { await apiRequest('/api/accounts',token,{method:'POST',body:JSON.stringify(account)}); setAccount({account_code:'',label:''});setMessage('Account added');await reload();onChanged() }
    catch(e){setMessage(e.message)}finally{setBusy(false)}
  }
  async function submitTx(e) {
    e.preventDefault(); setBusy(true); setMessage('')
    try {await apiRequest('/api/transactions',token,{method:'POST',body:JSON.stringify({...tx,occurred_at:new Date(tx.occurred_at).toISOString()})});setMessage('Transaction recorded');setTx(v=>({...v,transaction_id:'',amount:''}));await reload();onChanged()}
    catch(e){setMessage(e.message)}finally{setBusy(false)}
  }
  async function importCsv(e) {
    e.preventDefault();if(!file)return;setBusy(true);setMessage('')
    try {const fd=new FormData();fd.append('file',file);const res=await apiRequest('/api/transactions/import',token,{method:'POST',body:fd});setMessage(`${res.imported_rows} transactions imported · ${res.duplicate_rows} duplicates skipped`);setFile(null);e.target.reset();await reload();onChanged()}
    catch(e){setMessage(e.message)}finally{setBusy(false)}
  }
  return <section className="module-page">
    {message && <div className="feedback" role="status">{message}<button onClick={()=>setMessage('')} aria-label="Dismiss message">×</button></div>}
    {view === 'transactions' && <>
      <div className="module-heading"><div><h2>Transaction register</h2><p>Transactions are persisted in the local SQLite ledger.</p></div><span className="muted">{total} records</span></div>
      <div className="toolbar"><label>Transaction status <select value={status} onChange={e=>{setStatus(e.target.value);setPage(0)}}><option value="">All statuses</option><option value="completed">Completed</option><option value="pending">Pending</option><option value="failed">Failed</option></select></label><button className="button-light" onClick={reload}>Refresh records</button></div>
      <div className="table-scroll"><table className="data-table"><thead><tr><th>Transaction ID</th><th>From</th><th>To</th><th>Amount</th><th>Timestamp</th><th>Status</th></tr></thead><tbody>
        {items.map(i=><tr key={i.id}><td className="mono">{i.transaction_id}{i.transaction_id.startsWith('FGSIM_') && <span className="tiny-label">SIM</span>}</td><td className="mono">{i.sender_account}</td><td className="mono">{i.receiver_account}</td><td>{money(i.amount)}</td><td>{new Date(i.occurred_at).toLocaleString()}</td><td><span className={`status-tag ${i.status}`}>{i.status}</span></td></tr>)}
        {!items.length && <tr><td colSpan="6" className="table-empty">No matching transactions. Upload the sample CSV or run the simulator.</td></tr>}
      </tbody></table></div>
      <div className="pagination"><small>Showing {total ? page*20+1:0}–{Math.min(total,(page+1)*20)} of {total}</small><div><button className="button-light" onClick={()=>setPage(p=>p-1)} disabled={!page}>Previous</button><button className="button-light" onClick={()=>setPage(p=>p+1)} disabled={(page+1)*20>=total}>Next</button></div></div>
      <details className="form-drawer"><summary><PlusCircle size={16}/> Manually record a transaction</summary><form onSubmit={submitTx} className="form-grid">
        <label>Transaction ID<input required pattern="[A-Za-z0-9_-]+" value={tx.transaction_id} onChange={e=>setTx({...tx,transaction_id:e.target.value})}/></label>
        <label>Sender<select required value={tx.sender_account} onChange={e=>setTx({...tx,sender_account:e.target.value})}><option value="">Select account</option>{accounts.map(a=><option key={a.id}>{a.account_code}</option>)}</select></label>
        <label>Receiver<select required value={tx.receiver_account} onChange={e=>setTx({...tx,receiver_account:e.target.value})}><option value="">Select account</option>{accounts.map(a=><option key={a.id}>{a.account_code}</option>)}</select></label>
        <label>Amount (INR)<input required type="number" min="0.01" step="0.01" value={tx.amount} onChange={e=>setTx({...tx,amount:e.target.value})}/></label>
        <label>Date & time<input required type="datetime-local" value={tx.occurred_at} onChange={e=>setTx({...tx,occurred_at:e.target.value})}/></label>
        <label>Status<select value={tx.status} onChange={e=>setTx({...tx,status:e.target.value})}><option value="completed">Completed</option><option value="pending">Pending</option><option value="failed">Failed</option></select></label>
        <button type="submit" disabled={busy || accounts.length<2}>Save transaction</button>
      </form></details>
    </>}
    {view === 'accounts' && <><div className="module-heading"><div><h2>Account directory</h2><p>Owner-scoped synthetic financial entities.</p></div><span className="muted">{accounts.length} shown</span></div>
      <form className="inline-form" onSubmit={submitAccount}><label>Account code<input required minLength="2" maxLength="40" pattern="[A-Za-z0-9_-]+" placeholder="ACC1012" value={account.account_code} onChange={e=>setAccount({...account,account_code:e.target.value})}/></label><label>Label<input maxLength="100" placeholder="Optional description" value={account.label} onChange={e=>setAccount({...account,label:e.target.value})}/></label><button disabled={busy} type="submit"><PlusCircle size={15}/> Add account</button></form>
      <div className="table-scroll"><table className="data-table"><thead><tr><th>Account code</th><th>Label</th><th>Date created</th></tr></thead><tbody>{accounts.map(a=><tr key={a.id}><td className="mono">{a.account_code}</td><td>{a.label||'—'}</td><td>{new Date(a.created_at).toLocaleString()}</td></tr>)}{!accounts.length&&<tr><td className="table-empty" colSpan="3">No accounts available.</td></tr>}</tbody></table></div>
    </>}
    {view === 'imports' && <><div className="module-heading"><div><h2>CSV data import</h2><p>Validate and import synthetic transaction records in one batch.</p></div><div className="button-row"><a href="/sample_transactions.csv" download className="button-light"><Download size={15}/> 8-row sample</a><a href="/sample_transactions_1000.csv" download className="button-light"><Download size={15}/> 1,000-row sample</a></div></div>
      <form className="upload-panel" onSubmit={importCsv}><Upload size={27}/><strong>Upload synthetic transactions</strong><span>CSV, UTF-8 encoding. Up to 1,000 rows / 2 MB. All rows validated before commit.</span><input required type="file" accept=".csv,text/csv" onChange={e=>setFile(e.target.files?.[0]||null)}/><button disabled={busy||!file} type="submit">{busy?'Validating…':'Import CSV'}</button></form>
      <h3>Import history</h3><div className="table-scroll"><table className="data-table"><thead><tr><th>File</th><th>Rows</th><th>Imported</th><th>Duplicates</th><th>Time</th></tr></thead><tbody>{imports.map(i=><tr key={i.id}><td>{i.file_name}</td><td>{i.total_rows}</td><td>{i.imported_rows}</td><td>{i.duplicate_rows}</td><td>{new Date(i.created_at).toLocaleString()}</td></tr>)}{!imports.length&&<tr><td colSpan="5" className="table-empty">No imports yet.</td></tr>}</tbody></table></div>
    </>}
  </section>
}

export default function EvaluationPanel({ result, loading, error, onRefresh }) {
  const percent = n => `${((n || 0) * 100).toFixed(1)}%`
  return <section className="module">
    {error && <p className="feedback error">{error}</p>}
    {!result ? <p className="muted">{loading ? 'Computing confusion matrix and scores…' : 'Run evaluation to calculate performance.'}</p> : <>
      <div className="intel-cards three">
        {[['Precision',percent(result.precision)],['Recall',percent(result.recall)],['F1 score',percent(result.f1)]].map(([name,value])=><div className="intel-kpi" key={name}><small>{name}</small><strong>{value}</strong></div>)}
      </div>
      <div className="intel-two-cols">
        <div><h3>Confusion matrix</h3><div className="confusion-grid"><div className="confusion-cell good"><small>True positive</small><strong>{result.confusion_matrix.tp}</strong></div><div className="confusion-cell warn"><small>False positive</small><strong>{result.confusion_matrix.fp}</strong></div><div className="confusion-cell warn"><small>False negative</small><strong>{result.confusion_matrix.fn}</strong></div><div className="confusion-cell good"><small>True negative</small><strong>{result.confusion_matrix.tn}</strong></div></div></div>
        <div><h3>Scenario coverage ({result.cases} cases)</h3><div className="table-scroll"><table className="data-table"><thead><tr><th>Scenario</th><th>Cases</th><th>Flagged</th></tr></thead><tbody>{result.by_scenario.map(row=><tr key={row.label}><td>{row.label}</td><td>{row.cases}</td><td>{row.detected}</td></tr>)}</tbody></table></div></div>
      </div>
      <p className="callout"><strong>Evaluation limitations:</strong> {result.limitations}</p><p className="muted">Method: {result.methodology} Model: {result.model_version}.</p>
    </>}
  </section>
}

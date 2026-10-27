export default function EvaluationPanel({ result, loading, error, onRefresh }) {
  const percent = n => `${((n ?? 0) * 100).toFixed(1)}%`
  const stats = result ? [
    ['Precision', result.precision],
    ['Recall', result.recall],
    ['F1 score', result.f1],
    ['Specificity', result.specificity],
    ['False-positive rate', result.false_positive_rate],
    ['Accuracy (synthetic only)', result.accuracy]
  ] : []
  const labels = {
    ordinary: 'Ordinary payments', payroll: 'Legitimate payroll bursts',
    collections: 'Legitimate collections',
    legitimate_fast_chain: 'Legitimate rapid settlements',
    legitimate_settlement: 'Merchant clearing / aggregation',
    legitimate_circular: 'Legitimate cyclic settlements',
    circular: 'Suspicious circular movement',
    rapid: 'Suspicious rapid transfer', mule: 'Potential mule networks'
  }
  return <section className="module">
    <div className="module-heading">
      <div>
        <h2>Detection pipeline evaluation — synthetic stress test</h2>
        <p>Real NetworkX + synthetic-trained Extra Trees predictions on challenging labeled scenarios. This is not a real-world fraud accuracy measurement; use the figures exactly as measured.</p>
      </div>
      <button onClick={onRefresh} className="button-light" disabled={loading}>{loading ? 'Evaluating…' : 'Run evaluation'}</button>
    </div>
    {error && <p className="feedback error">{error}</p>}
    {!result ? <p className="muted">{loading ? 'Evaluating synthetic cases…' : 'Run evaluation to calculate results.'}</p> : <>
      <p className="callout"><strong>Research prototype:</strong> Results include legitimate transaction patterns that resemble financial crime and suspicious cases that are intentionally difficult to detect. A lower score highlights weaknesses to improve; we do not adjust results to make the model look better.</p>
      <p className="callout"><strong>Development goal:</strong> 78% F1 on a trustworthy holdout dataset. <strong>Actual measured F1:</strong> {percent(result.f1)}. The goal is not a measured result.</p>
      <div className="intel-cards three">
        {stats.map(([name, value]) => <div className="intel-kpi" key={name}><small>{name}</small><strong>{percent(value)}</strong></div>)}
      </div>
      <div className="intel-two-cols">
        <div>
          <h3>Confusion matrix — {result.cases} labeled cases</h3>
          <div className="confusion-grid">
            <div className="confusion-cell good"><small>True positive</small><strong>{result.confusion_matrix.tp}</strong></div>
            <div className="confusion-cell warn"><small>False positive</small><strong>{result.confusion_matrix.fp}</strong></div>
            <div className="confusion-cell warn"><small>False negative</small><strong>{result.confusion_matrix.fn}</strong></div>
            <div className="confusion-cell good"><small>True negative</small><strong>{result.confusion_matrix.tn}</strong></div>
          </div>
        </div>
        <div>
          <h3>Scenario coverage</h3>
          <div className="table-scroll"><table className="data-table"><thead><tr><th>Scenario</th><th>Cases</th><th>Flagged</th><th>Detection rate</th></tr></thead><tbody>
            {result.by_scenario.map(row => <tr key={row.label}>
              <td>{labels[row.label] || row.label}</td><td>{row.cases}</td><td>{row.detected}</td><td>{percent(row.cases ? row.detected / row.cases : 0)}</td>
            </tr>)}
          </tbody></table></div>
        </div>
      </div>
      <p className="callout"><strong>Limitations:</strong> {result.limitations}</p>
      <p className="muted">Method: {result.methodology} Model: {result.model_version}.</p>
    </>}
  </section>
}

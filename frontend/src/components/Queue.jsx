import DecisionChip from './DecisionChip.jsx'

const money = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
const time = (iso) => new Date(iso).toLocaleTimeString('en-IN', { hour12: false })

export default function Queue({ rows, selectedId, onSelect, filter, onFilter }) {
  return (
    <section className="card queue">
      <header className="queue-head">
        <h2>Live application stream</h2>
        <div className="filters" role="group" aria-label="Filter by decision">
          {['ALL', 'ALLOW', 'STEP_UP', 'REVIEW', 'BLOCK'].map((option) => (
            <button key={option} className={`filter ${filter === option ? 'on' : ''}`}
                    onClick={() => onFilter(option)}>
              {option.replace('_', ' ')}
            </button>
          ))}
        </div>
      </header>

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Time</th><th>Applicant</th><th className="num">Amount</th>
              <th>Risk</th><th>Decision</th><th>Leading indicator</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan="6" className="muted pad">
                No applications yet — run the traffic simulator (see README).
              </td></tr>
            )}
            {rows.map((row) => (
              <tr key={row.application_id}
                  className={row.application_id === selectedId ? 'selected' : ''}
                  onClick={() => onSelect(row.application_id)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && onSelect(row.application_id)}>
                <td className="mono muted">{time(row.created_at)}</td>
                <td>
                  {row.applicant_name}
                  {row.label === 1 && <span className="tag tag-fraud">confirmed fraud</span>}
                  {row.label === 0 && <span className="tag">cleared</span>}
                </td>
                <td className="num mono">{money.format(row.amount)}</td>
                <td><RiskMeter score={row.risk_score} decision={row.decision} /></td>
                <td><DecisionChip decision={row.decision} /></td>
                <td className="muted reason">{row.top_reason || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export function RiskMeter({ score, decision }) {
  return (
    <span className="meter" title={`Risk ${score.toFixed(2)}`}>
      <span className={`meter-fill seg-${decision}`} style={{ width: `${score * 100}%` }} />
      <span className="meter-value mono">{score.toFixed(2)}</span>
    </span>
  )
}

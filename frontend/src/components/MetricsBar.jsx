import DecisionChip from './DecisionChip.jsx'

const ORDER = ['ALLOW', 'STEP_UP', 'REVIEW', 'BLOCK']
const pct = (value) => `${(value * 100).toFixed(1)}%`

export default function MetricsBar({ metrics, model }) {
  if (!metrics) return <section className="kpis muted">Loading metrics…</section>
  const total = Math.max(metrics.total_applications, 1)

  return (
    <>
      <section className="kpis">
        <Kpi label="Applications scored" value={metrics.total_applications} sub={`last ${metrics.window_hours}h`} />
        <Kpi label="Straight-through" value={pct(metrics.frictionless_rate)} sub="no customer friction" />
        <Kpi label="Sent to review" value={pct(metrics.review_rate)} sub="review + blocked" />
        <Kpi label="Decision latency p95" value={`${metrics.p95_latency_ms.toFixed(0)} ms`} sub="synchronous path" />
        <Kpi label="Model recall" value={pct(model?.metrics?.recall_at_review ?? 0)}
             sub={`precision ${pct(model?.metrics?.precision_at_review ?? 0)}`} />
      </section>

      <section className="card">
        <h2>Decision mix</h2>
        <div className="mix" role="img"
             aria-label={ORDER.map((d) => `${d} ${metrics.by_decision[d] || 0}`).join(', ')}>
          {ORDER.map((decision) => {
            const count = metrics.by_decision[decision] || 0
            if (!count) return null
            return (
              <span key={decision} className={`mix-seg seg-${decision}`}
                    style={{ flexGrow: count }} title={`${decision}: ${count}`} />
            )
          })}
        </div>
        <div className="mix-legend">
          {ORDER.map((decision) => (
            <span key={decision} className="legend-item">
              <DecisionChip decision={decision} />
              <b>{metrics.by_decision[decision] || 0}</b>
              <span className="muted small">{pct((metrics.by_decision[decision] || 0) / total)}</span>
            </span>
          ))}
        </div>
      </section>
    </>
  )
}

function Kpi({ label, value, sub }) {
  return (
    <div className="card kpi">
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value}</strong>
      <span className="muted small">{sub}</span>
    </div>
  )
}

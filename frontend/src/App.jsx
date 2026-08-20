import { useCallback, useEffect, useState } from 'react'
import { clearSession, getMetrics, getModelInfo, getRole, getToken, listApplications, retrain } from './api.js'
import CaseDetail from './components/CaseDetail.jsx'
import Login from './components/Login.jsx'
import MetricsBar from './components/MetricsBar.jsx'
import Queue from './components/Queue.jsx'

const REFRESH_MS = 2000

export default function App() {
  const [signedIn, setSignedIn] = useState(Boolean(getToken()))
  const [rows, setRows] = useState([])
  const [metrics, setMetrics] = useState(null)
  const [model, setModel] = useState(null)
  const [selected, setSelected] = useState(null)
  const [filter, setFilter] = useState('ALL')
  const [error, setError] = useState('')
  const [retraining, setRetraining] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const [applications, liveMetrics, modelInfo] = await Promise.all([
        listApplications(), getMetrics(), getModelInfo(),
      ])
      setRows(applications)
      setMetrics(liveMetrics)
      setModel(modelInfo)
      setError('')
    } catch (err) {
      setError(err.message)
      if (err.message.includes('sign in')) setSignedIn(false)
    }
  }, [])

  useEffect(() => {
    if (!signedIn) return
    refresh()
    const timer = setInterval(refresh, REFRESH_MS)   // the API is the source of truth
    return () => clearInterval(timer)
  }, [signedIn, refresh])

  if (!signedIn) return <Login onSignedIn={() => setSignedIn(true)} />

  const visible = filter === 'ALL' ? rows : rows.filter((row) => row.decision === filter)

  async function onRetrain() {
    setRetraining('running')
    try {
      const result = await retrain()
      setRetraining(`Retrained on ${result.labelled_cases} analyst-labelled cases · ` +
        `ROC-AUC ${result.previous_metrics.roc_auc} → ${result.new_metrics.roc_auc}`)
      refresh()
    } catch (err) {
      setRetraining(err.message)
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <div>
            <h1>Sentinel</h1>
            <p className="muted small">Real-time fraud detection · digital lending</p>
          </div>
        </div>
        <div className="topbar-right">
          {model && (
            <span className="muted small">
              model {model.metrics.roc_auc} ROC-AUC · trained {new Date(model.trained_at).toLocaleString('en-IN')} ·
              LLM {model.llm.live ? `live (${model.llm.model})` : 'offline — deterministic fallback'}
            </span>
          )}
          {getRole() === 'admin' && (
            <button onClick={onRetrain} disabled={retraining === 'running'}>
              {retraining === 'running' ? 'Retraining…' : 'Retrain from feedback'}
            </button>
          )}
          <button className="ghost" onClick={() => { clearSession(); setSignedIn(false) }}>Sign out</button>
        </div>
      </header>

      {error && <p className="error banner" role="alert">{error}</p>}
      {retraining && retraining !== 'running' && <p className="banner ok">{retraining}</p>}

      <main>
        <MetricsBar metrics={metrics} model={model} />
        <div className="split">
          <Queue rows={visible} selectedId={selected} onSelect={setSelected}
                 filter={filter} onFilter={setFilter} />
          <CaseDetail applicationId={selected} onReviewed={refresh} />
        </div>
      </main>
    </div>
  )
}

import { useState } from 'react'
import { login } from '../api.js'

export default function Login({ onSignedIn }) {
  const [email, setEmail] = useState('analyst@sentinel.local')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      onSignedIn(await login(email, password))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-shell">
      <form className="card login-card" onSubmit={submit}>
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <div>
            <h1>Sentinel</h1>
            <p className="muted">Fraud operations console — digital lending</p>
          </div>
        </div>
        <label htmlFor="email">Work email</label>
        <input id="email" type="email" value={email} autoComplete="username"
               onChange={(e) => setEmail(e.target.value)} required />
        <label htmlFor="password">Password</label>
        <input id="password" type="password" value={password} autoComplete="current-password"
               onChange={(e) => setPassword(e.target.value)} required minLength={8} />
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" type="submit" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
        <p className="muted small">
          Credentials are seeded from environment variables at first start — see README.
        </p>
      </form>
    </div>
  )
}

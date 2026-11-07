import { useEffect, useState } from 'react'
import type { Fixture } from '../api'
import { api } from '../api'
import { MatchCard } from '../components/MatchCard'

export function Predictor({ leagues }: { leagues: { code: string; name: string }[] }) {
  const [teams, setTeams] = useState<Record<string, string[]>>({})
  const [league, setLeague] = useState('E0')
  const [home, setHome] = useState('')
  const [away, setAway] = useState('')
  const [res, setRes] = useState<Fixture | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.teams().then(setTeams, () => {})
  }, [])

  const list = teams[league] ?? []
  useEffect(() => {
    setHome(list[0] ?? '')
    setAway(list[1] ?? '')
    setRes(null)
  }, [league, teams]) // eslint-disable-line react-hooks/exhaustive-deps

  const run = async () => {
    setErr(null)
    setBusy(true)
    try {
      setRes(await api.predict(home, away, league))
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="stack">
      <p className="muted small">
        Pick any two teams from the current season. The prediction uses each side’s latest form as if they met today
        (no bookmaker odds, so no edge is shown).
      </p>
      <div className="filters">
        <select value={league} onChange={(e) => setLeague(e.target.value)}>
          {leagues.map((l) => (
            <option key={l.code} value={l.code}>
              {l.name}
            </option>
          ))}
        </select>
        <select value={home} onChange={(e) => setHome(e.target.value)} aria-label="Home team">
          {list.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
        <span className="muted">v</span>
        <select value={away} onChange={(e) => setAway(e.target.value)} aria-label="Away team">
          {list.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
        <button className="btn" onClick={run} disabled={busy || !home || !away || home === away}>
          {busy ? 'Predicting…' : 'Predict'}
        </button>
      </div>
      {err && <div className="notice error">{err}</div>}
      {res && <MatchCard f={res} />}
    </section>
  )
}

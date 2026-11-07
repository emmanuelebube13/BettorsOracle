import { useEffect, useMemo, useState } from 'react'
import type { Fixture, Market } from '../api'
import { api } from '../api'
import { MatchCard } from '../components/MatchCard'

export function Fixtures({ league, onLog }: { league: string; onLog: (match: string, m: Market) => void }) {
  const [fx, setFx] = useState<Fixture[] | null>(null)
  const [q, setQ] = useState('')
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    setFx(null)
    api.fixtures(league || undefined).then(setFx, (e) => setErr(String(e.message ?? e)))
  }, [league])

  const shown = useMemo(
    () => (fx ?? []).filter((f) => `${f.home} ${f.away}`.toLowerCase().includes(q.toLowerCase())),
    [fx, q],
  )

  return (
    <section className="stack">
      <div className="filters">
        <input type="text" placeholder="Search team…" value={q} onChange={(e) => setQ(e.target.value)} />
        {fx && <span className="small muted">{shown.length} upcoming matches</span>}
      </div>
      {err && <div className="notice error">{err}</div>}
      {fx === null && !err && <p className="muted">Loading…</p>}
      {fx && fx.length === 0 && (
        <p className="muted">No upcoming fixtures loaded. Use “Refresh data” to pull the latest fixture list.</p>
      )}
      {shown.map((f) => (
        <MatchCard key={`${f.league}-${f.home}-${f.away}`} f={f} onLog={onLog} />
      ))}
    </section>
  )
}

import { useEffect, useState } from 'react'
import type { Market, TopBet } from '../api'
import { api, pct, signedPct } from '../api'

export function TopBets({ league, onLog }: { league: string; onLog: (match: string, m: Market) => void }) {
  const [minProb, setMinProb] = useState(0.7)
  const [onlyEdge, setOnlyEdge] = useState(false)
  const [bets, setBets] = useState<TopBet[] | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    setBets(null)
    api.topBets(minProb, league || undefined).then(setBets, (e) => setErr(String(e.message ?? e)))
  }, [minProb, league])

  const shown = (bets ?? []).filter((b) => !onlyEdge || b.value)

  return (
    <section className="stack">
      <div className="notice small">
        Top bets are upcoming markets where the model gives at least {pct(minProb)}. These hit often, but in the
        backtest they still <strong>lost money after bookmaker margin</strong>; see the Performance tab. "Edge" means
        the model disagrees with the market, not that the bet is profitable.
      </div>
      <div className="filters">
        <label className="small">
          Min probability{' '}
          <select value={minProb} onChange={(e) => setMinProb(Number(e.target.value))}>
            {[0.6, 0.65, 0.7, 0.75, 0.8, 0.85].map((p) => (
              <option key={p} value={p}>
                {pct(p)}
              </option>
            ))}
          </select>
        </label>
        <label className="small row" style={{ gap: 6 }}>
          <input type="checkbox" checked={onlyEdge} onChange={(e) => setOnlyEdge(e.target.checked)} />
          Only where the model sees positive edge
        </label>
      </div>
      {err && <div className="notice error">{err}</div>}
      {bets === null && !err && <p className="muted">Loading…</p>}
      {bets && shown.length === 0 && <p className="muted">No picks match these filters right now.</p>}
      {shown.length > 0 && (
        <div className="card table-wrap">
          <table>
            <thead>
              <tr>
                <th>Kick-off</th>
                <th>Match</th>
                <th>Pick</th>
                <th className="num">Model</th>
                <th className="num">Odds</th>
                <th className="num">Edge</th>
                <th className="num" title="Quarter-Kelly, capped at 5% of bankroll">
                  Stake
                </th>
                <th />
              </tr>
            </thead>
            <tbody>
              {shown.map((b) => (
                <tr key={`${b.home}-${b.away}`}>
                  <td className="small">
                    {b.date}
                    <div className="muted">{b.time}</div>
                  </td>
                  <td>
                    {b.home} v {b.away}
                    <div className="small muted">{b.league_name}</div>
                  </td>
                  <td>{b.market}</td>
                  <td className="num">{pct(b.prob, 1)}</td>
                  <td className="num">{b.odds?.toFixed(2)}</td>
                  <td className="num">{signedPct(b.edge)}</td>
                  <td className="num">{b.kelly_pct ? pct(b.kelly_pct, 1) : '–'}</td>
                  <td className="num">
                    <button className="btn ghost small" onClick={() => onLog(`${b.home} v ${b.away}`, b)}>
                      Log
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

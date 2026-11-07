import type { Fixture, Market } from '../api'
import { pct, signedPct } from '../api'

const METRIC_LABELS: Record<string, string> = {
  form: 'Form index',
  avg_scored: 'Avg scored',
  avg_conceded: 'Avg conceded',
  wins: 'Wins (last 11)',
  draws: 'Draws',
  losses: 'Losses',
  goal_ratio: 'Goal ratio',
  goal_diff: 'Goal difference',
  avg_sot: 'Shots on target',
  h2h_wins: 'H2H wins',
}

const fmt = (m: string, v: number | null) => {
  if (v == null) return '–'
  if (m === 'form') return pct(v)
  return Number.isInteger(v) ? String(v) : v.toFixed(2)
}

export function ProbBar({ probs }: { probs: Fixture['probs'] }) {
  const parts = [
    { key: 'Home', v: probs.home, c: 'var(--series-home)' },
    { key: 'Draw', v: probs.draw, c: 'var(--series-draw)' },
    { key: 'Away', v: probs.away, c: 'var(--series-away)' },
  ]
  return (
    <div>
      <div className="probbar" role="img" aria-label={parts.map((p) => `${p.key} ${pct(p.v)}`).join(', ')}>
        {parts.map((p) => (
          <span key={p.key} title={`${p.key}: ${pct(p.v, 1)}`} style={{ width: `${p.v * 100}%`, background: p.c }} />
        ))}
      </div>
      <div className="legend">
        {parts.map((p) => (
          <span key={p.key}>
            <i style={{ background: p.c }} />
            {p.key} <strong>{pct(p.v)}</strong>
          </span>
        ))}
        <span>Over 2.5 <strong>{pct(probs.over25)}</strong></span>
        <span>BTTS <strong>{pct(probs.btts)}</strong></span>
      </div>
    </div>
  )
}

const TIER_LABEL = { high: 'High', moderate: 'Moderate', avoid: 'Avoid' }

export function MatchCard({ f, onLog }: { f: Fixture; onLog?: (match: string, m: Market) => void }) {
  const o = f.oracle
  const pickName = o.pick === 'H' ? f.home : o.pick === 'A' ? f.away : 'Draw'
  return (
    <article className="card">
      <div className="match-head">
        <div className="teams">
          {f.home} <span className="muted">v</span> {f.away}
        </div>
        <div className="row small muted">
          <span>{f.league_name}</span>
          <span>
            {f.date}
            {f.time ? ` · ${f.time}` : ''}
          </span>
        </div>
      </div>
      {!f.enough_history && (
        <div className="notice small" style={{ marginTop: 8 }}>
          Limited history for one of these teams in this league; treat this prediction with extra caution.
        </div>
      )}
      <ProbBar probs={f.probs} />
      <div className="row small" style={{ marginTop: 6 }}>
        <span className="badge">
          Oracle rules: {pickName} ({o.votes.home}–{o.votes.away} metric votes)
        </span>
        <span className="badge">
          Double chance {f.home}: {TIER_LABEL[o.double_chance.home.tier]} ({o.double_chance.home.met.length}/
          {o.max_criteria})
        </span>
        <span className="badge">
          Double chance {f.away}: {TIER_LABEL[o.double_chance.away.tier]} ({o.double_chance.away.met.length}/
          {o.max_criteria})
        </span>
      </div>

      <details>
        <summary>Markets, odds &amp; team metrics</summary>
        <div className="cols">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Market</th>
                  <th className="num">Model</th>
                  <th className="num">Fair</th>
                  <th className="num">Odds</th>
                  <th className="num" title="Model probability × odds − 1. Positive = model disagrees with the market.">
                    Edge
                  </th>
                  {onLog && <th />}
                </tr>
              </thead>
              <tbody>
                {f.markets.map((m) => (
                  <tr key={m.market}>
                    <td>{m.market}</td>
                    <td className="num">{pct(m.prob, 1)}</td>
                    <td className="num">{m.fair_odds?.toFixed(2) ?? '–'}</td>
                    <td className="num">{m.odds?.toFixed(2) ?? '–'}</td>
                    <td className="num">{signedPct(m.edge)}</td>
                    {onLog && (
                      <td className="num">
                        {m.odds && (
                          <button className="btn ghost small" onClick={() => onLog(`${f.home} v ${f.away}`, m)}>
                            Log
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Metric (last 11)</th>
                  <th className="num">{f.home}</th>
                  <th className="num">{f.away}</th>
                </tr>
              </thead>
              <tbody>
                {o.metrics.map((m) => (
                  <tr key={m.metric}>
                    <td>{METRIC_LABELS[m.metric] ?? m.metric}</td>
                    <td className={`num ${m.favours === 'home' ? 'fav-home' : 'muted'}`}>{fmt(m.metric, m.home)}</td>
                    <td className={`num ${m.favours === 'away' ? 'fav-home' : 'muted'}`}>{fmt(m.metric, m.away)}</td>
                  </tr>
                ))}
                <tr>
                  <td>BTTS rate</td>
                  <td className="num muted">{pct(f.stats.home.btts_rate)}</td>
                  <td className="num muted">{pct(f.stats.away.btts_rate)}</td>
                </tr>
                <tr>
                  <td>Over 2.5 rate</td>
                  <td className="num muted">{pct(f.stats.home.over25_rate)}</td>
                  <td className="num muted">{pct(f.stats.away.over25_rate)}</td>
                </tr>
              </tbody>
            </table>
            <p className="small muted">Bold = the side that metric favours. H2H covers the last {f.h2h.games} meetings.</p>
          </div>
        </div>
      </details>
    </article>
  )
}

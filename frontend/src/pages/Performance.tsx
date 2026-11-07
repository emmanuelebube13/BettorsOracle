import { useEffect, useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Backtest } from '../api'
import { api, pct, signedPct } from '../api'

export function Performance() {
  const [bt, setBt] = useState<Backtest | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    api.backtest().then(setBt, (e) => setErr(String(e.message ?? e)))
  }, [])

  if (err) return <div className="notice error">{err}</div>
  if (!bt) return <p className="muted">Loading…</p>

  const s = bt.seasons
  const done = s.slice(0, -1).length ? s.slice(0, -1) : s
  const avg = (f: (x: (typeof s)[number]) => number) => done.reduce((a, x) => a + f(x), 0) / done.length
  const latest = s[s.length - 2] ?? s[s.length - 1]

  return (
    <section className="stack">
      <p className="muted small">
        Walk-forward backtest: every season is predicted by a model trained only on earlier seasons, then compared with
        the bookmakers’ closing-average odds. Averages below cover completed seasons.
      </p>
      <div className="grid-tiles">
        <div className="card tile">
          <div className="label">Model accuracy (1X2)</div>
          <div className="value">{pct(avg((x) => x.model.accuracy), 1)}</div>
          <div className="sub">Market: {pct(avg((x) => x.market?.accuracy ?? 0), 1)}</div>
        </div>
        <div className="card tile">
          <div className="label">Excel rules accuracy</div>
          <div className="value">{pct(avg((x) => x.rules_accuracy), 1)}</div>
          <div className="sub">The original spreadsheet logic</div>
        </div>
        <div className="card tile">
          <div className="label">Top bets (≥{pct(bt.top_bet_threshold)}) hit rate</div>
          <div className="value">{pct(avg((x) => x.top_bets.hit_rate ?? 0), 1)}</div>
          <div className="sub">ROI {signedPct(avg((x) => x.top_bets.roi ?? 0))} flat stakes</div>
        </div>
        <div className="card tile">
          <div className="label">“Value” bets (edge &gt; 5%) ROI</div>
          <div className="value">{signedPct(avg((x) => x.value_bets.roi ?? 0))}</div>
          <div className="sub">Hit rate {pct(avg((x) => x.value_bets.hit_rate ?? 0), 1)}</div>
        </div>
      </div>

      <div className="notice small">
        <strong>Verdict:</strong> the model is well calibrated but does not beat the bookmakers. Its probabilities are
        honest estimates, not a money machine. Improving on the market will need better data (injuries, lineups,
        expected goals) before any betting strategy here is profitable.
      </div>

      <div className="card">
        <h3 style={{ margin: '0 0 4px' }}>Calibration, {latest.season}</h3>
        <p className="small muted" style={{ marginTop: 0 }}>
          When the model says X%, how often does it happen? Points on the dashed diagonal mean perfectly calibrated.
        </p>
        <div style={{ width: '100%', height: 280 }}>
          <ResponsiveContainer>
            <LineChart data={latest.calibration} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis
                dataKey="predicted"
                type="number"
                domain={[0, 1]}
                tickFormatter={(v) => pct(v)}
                stroke="var(--text-muted)"
                tick={{ fontSize: 12 }}
              />
              <YAxis domain={[0, 1]} tickFormatter={(v) => pct(v)} stroke="var(--text-muted)" tick={{ fontSize: 12 }} />
              <ReferenceLine
                segment={[
                  { x: 0, y: 0 },
                  { x: 1, y: 1 },
                ]}
                stroke="var(--text-muted)"
                strokeDasharray="4 4"
              />
              <Tooltip
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <div className="chart-tooltip">
                      Predicted {pct(payload[0].payload.predicted, 1)}
                      <br />
                      Happened <strong>{pct(payload[0].payload.actual, 1)}</strong>
                      <br />
                      <span className="muted">{payload[0].payload.n.toLocaleString()} market predictions</span>
                    </div>
                  ) : null
                }
              />
              <Line
                dataKey="actual"
                stroke="var(--series-home)"
                strokeWidth={2}
                dot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface-1)', fill: 'var(--series-home)' }}
                activeDot={{ r: 6 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Season</th>
              <th className="num">Matches</th>
              <th className="num">Model acc.</th>
              <th className="num">Market acc.</th>
              <th className="num">Rules acc.</th>
              <th className="num">Model log loss</th>
              <th className="num">Market log loss</th>
              <th className="num">Top bets</th>
              <th className="num">Top ROI</th>
              <th className="num">Value ROI</th>
            </tr>
          </thead>
          <tbody>
            {s.map((x) => (
              <tr key={x.season}>
                <td>{x.season}</td>
                <td className="num">{x.matches}</td>
                <td className="num">{pct(x.model.accuracy, 1)}</td>
                <td className="num">{pct(x.market?.accuracy, 1)}</td>
                <td className="num">{pct(x.rules_accuracy, 1)}</td>
                <td className="num">{x.model.log_loss.toFixed(3)}</td>
                <td className="num">{x.market?.log_loss.toFixed(3) ?? '–'}</td>
                <td className="num">{x.top_bets.bets}</td>
                <td className="num">{signedPct(x.top_bets.roi)}</td>
                <td className="num">{signedPct(x.value_bets.roi)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="small muted">Lower log loss is better. The last row is the season in progress.</p>
      </div>
    </section>
  )
}

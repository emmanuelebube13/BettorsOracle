import { useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Bankroll, Bet } from '../api'
import { api, money, pct, signedPct, STATIC } from '../api'

const STATUS_LABEL: Record<Bet['status'], string> = { pending: 'Pending', won: '✓ Won', lost: '✕ Lost', void: 'Void' }

export function BankrollPage({ data, reload }: { data: Bankroll | null; reload: () => void }) {
  const [form, setForm] = useState({ match: '', market: '', odds: '', stake: '' })
  const [start, setStart] = useState('')
  const [err, setErr] = useState<string | null>(null)

  if (!data) return <p className="muted">Loading…</p>

  const act = (p: Promise<unknown>) =>
    p.then(reload, (e) => setErr((e as Error).message))

  const add = (e: React.FormEvent) => {
    e.preventDefault()
    setErr(null)
    act(
      api.addBet({ match: form.match, market: form.market, odds: Number(form.odds), stake: Number(form.stake) }).then(
        () => setForm({ match: '', market: '', odds: '', stake: '' }),
      ),
    )
  }

  const series = data.series.map((p, i) => ({ i, ...p }))

  return (
    <section className="stack">
      {STATIC && (
        <div className="notice small">
          Your bets are saved in this browser only. They aren’t uploaded anywhere, and clearing site data erases them.
        </div>
      )}
      <div className="grid-tiles">
        <div className="card tile">
          <div className="label">Bankroll</div>
          <div className="value">{money(data.bankroll)}</div>
          <div className="sub">Started at {money(data.starting_bankroll)}</div>
        </div>
        <div className="card tile">
          <div className="label">Profit</div>
          <div className="value">{money(data.profit)}</div>
          <div className="sub">ROI {signedPct(data.roi)}</div>
        </div>
        <div className="card tile">
          <div className="label">Hit rate</div>
          <div className="value">{pct(data.hit_rate, 1)}</div>
          <div className="sub">{data.settled} settled · {data.pending} pending</div>
        </div>
        <div className="card tile">
          <div className="label">Max drawdown</div>
          <div className="value">{pct(data.max_drawdown, 1)}</div>
          <div className="sub">Available: {money(data.available)}</div>
        </div>
      </div>

      <div className="card">
        <h3 style={{ margin: '0 0 8px' }}>Account growth</h3>
        {series.length < 2 ? (
          <p className="muted small">Settle a few bets to see your bankroll over time.</p>
        ) : (
          <div style={{ width: '100%', height: 260 }}>
            <ResponsiveContainer>
              <LineChart data={series} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="i" stroke="var(--text-muted)" tick={{ fontSize: 12 }} tickFormatter={(v) => `#${v}`} />
                <YAxis stroke="var(--text-muted)" tick={{ fontSize: 12 }} tickFormatter={(v) => money(v)} width={80} />
                <Tooltip
                  cursor={{ stroke: 'var(--text-muted)', strokeDasharray: '3 3' }}
                  content={({ active, payload }) =>
                    active && payload?.length ? (
                      <div className="chart-tooltip">
                        {payload[0].payload.i === 0 ? 'Start' : `After bet #${payload[0].payload.i}`}
                        <br />
                        <strong>{money(payload[0].payload.bankroll)}</strong>
                      </div>
                    ) : null
                  }
                />
                <Line
                  dataKey="bankroll"
                  stroke="var(--series-home)"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 5 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="cols">
        <form className="card stack" onSubmit={add}>
          <h3 style={{ margin: 0 }}>Log a bet</h3>
          <input type="text" required placeholder="Match (e.g. Arsenal v Hull)" value={form.match}
            onChange={(e) => setForm({ ...form, match: e.target.value })} />
          <input type="text" required placeholder="Market (e.g. Home win)" value={form.market}
            onChange={(e) => setForm({ ...form, market: e.target.value })} />
          <div className="row">
            <input type="number" required min="1.01" step="0.01" placeholder="Odds" value={form.odds}
              onChange={(e) => setForm({ ...form, odds: e.target.value })} style={{ flex: 1 }} />
            <input type="number" required min="0.01" step="0.01" placeholder="Stake" value={form.stake}
              onChange={(e) => setForm({ ...form, stake: e.target.value })} style={{ flex: 1 }} />
          </div>
          <button className="btn" type="submit">Add bet</button>
        </form>
        <div className="card stack">
          <h3 style={{ margin: 0 }}>Starting bankroll</h3>
          <p className="small muted" style={{ margin: 0 }}>
            Stakes suggested elsewhere in the app are quarter-Kelly, capped at 5% of what’s available.
          </p>
          <div className="row">
            <input type="number" min="1" step="1" placeholder={String(data.starting_bankroll)} value={start}
              onChange={(e) => setStart(e.target.value)} style={{ flex: 1 }} />
            <button className="btn ghost" disabled={!start}
              onClick={() => act(api.setBankroll(Number(start)).then(() => setStart('')))}>
              Save
            </button>
          </div>
        </div>
      </div>

      {err && <div className="notice error">{err}</div>}

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Placed</th>
              <th>Match</th>
              <th>Market</th>
              <th className="num">Odds</th>
              <th className="num">Stake</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {data.bets.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">No bets logged yet. Use “Log” on any pick or the form above.</td>
              </tr>
            )}
            {data.bets.map((b) => (
              <tr key={b.id}>
                <td className="small muted">{b.placed_at.slice(0, 10)}</td>
                <td>{b.match}</td>
                <td>{b.market}</td>
                <td className="num">{b.odds.toFixed(2)}</td>
                <td className="num">{money(b.stake)}</td>
                <td>
                  <span className={`badge ${b.status === 'won' ? 'good' : ''}`}>{STATUS_LABEL[b.status]}</span>
                </td>
                <td className="num">
                  <div className="row" style={{ gap: 4, justifyContent: 'flex-end' }}>
                    {b.status === 'pending' ? (
                      <>
                        <button className="btn ghost small" onClick={() => act(api.settleBet(b.id, 'won'))}>Won</button>
                        <button className="btn ghost small" onClick={() => act(api.settleBet(b.id, 'lost'))}>Lost</button>
                        <button className="btn ghost small" onClick={() => act(api.settleBet(b.id, 'void'))}>Void</button>
                      </>
                    ) : (
                      <button className="btn ghost small" onClick={() => act(api.settleBet(b.id, 'pending'))}>Undo</button>
                    )}
                    <button className="btn ghost small" aria-label="Delete bet"
                      onClick={() => confirm('Delete this bet?') && act(api.deleteBet(b.id))}>
                      ✕
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

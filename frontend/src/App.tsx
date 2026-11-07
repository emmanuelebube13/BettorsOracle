import { useCallback, useEffect, useState } from 'react'
import type { Bankroll, Health, Market } from './api'
import { api, money, STATIC } from './api'
import { BankrollPage } from './pages/BankrollPage'
import { Fixtures } from './pages/Fixtures'
import { Performance } from './pages/Performance'
import { Predictor } from './pages/Predictor'
import { TopBets } from './pages/TopBets'

const TABS = ['Top bets', 'Fixtures', 'Predictor', 'Performance', 'Bankroll'] as const
type Tab = (typeof TABS)[number]

export default function App() {
  const [tab, setTab] = useState<Tab>('Top bets')
  const [league, setLeague] = useState('')
  const [leagues, setLeagues] = useState<{ code: string; name: string }[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [bank, setBank] = useState<Bankroll | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  const loadBank = useCallback(() => api.bankroll().then(setBank, () => {}), [])

  useEffect(() => {
    api.leagues().then(setLeagues, () => {})
    api.health().then(setHealth, () => setHealth(null))
    loadBank()
  }, [loadBank])

  const flash = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 3500)
  }

  const logBet = async (match: string, m: Market) => {
    const available = bank?.available ?? 0
    const suggested = Math.max(0, Math.round(available * m.kelly_pct * 100) / 100)
    const hint = suggested
      ? `Suggested stake (quarter-Kelly): ${money(suggested)}`
      : 'The model sees no edge at this price, so the suggested stake is 0.'
    const input = prompt(`${match}: ${m.market} @ ${m.odds}\n${hint}\n\nStake:`, suggested ? String(suggested) : '')
    if (!input) return
    const stake = Number(input)
    if (!(stake > 0)) return flash('Stake must be a positive number.')
    try {
      await api.addBet({ match, market: m.market, odds: m.odds!, stake })
      await loadBank()
      flash(`Logged ${money(stake)} on ${m.market}, ${match}`)
    } catch (e) {
      flash((e as Error).message)
    }
  }

  const refresh = async () => {
    setRefreshing(true)
    try {
      await api.refresh(localStorage.getItem('bo_admin_token') ?? undefined)
      setHealth(await api.health())
      setNonce((n) => n + 1)
      flash('Data refreshed and model retrained.')
    } catch (e) {
      const msg = (e as Error).message
      if (msg.includes('token')) {
        const t = prompt('Admin token:')
        if (t) {
          try { localStorage.setItem('bo_admin_token', t) } catch { /* storage unavailable */ }
        }
      }
      flash(`Refresh failed: ${msg}`)
    } finally {
      setRefreshing(false)
    }
  }

  const showLeague = tab === 'Top bets' || tab === 'Fixtures'

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="dot" aria-hidden /> BettorsOracle
        </div>
        <div className="row small">
          {health?.fixtures_updated && (
            <span className="meta" title={STATIC ? 'Refreshed automatically every 6 hours' : undefined}>
              Data updated {new Date(health.fixtures_updated).toLocaleString()}
            </span>
          )}
          {bank && <span className="badge">Bankroll {money(bank.bankroll)}</span>}
          {!STATIC && (
            <button className="btn ghost small" onClick={refresh} disabled={refreshing}>
              {refreshing ? 'Refreshing… (about 1 min)' : 'Refresh data'}
            </button>
          )}
        </div>
      </header>

      {health && !health.ready && (
        <div className="notice" style={{ marginBottom: 16 }}>
          No data loaded yet. Click <strong>Refresh data</strong> to download match history and train the model.
        </div>
      )}
      {!health && (
        <div className="notice error" style={{ marginBottom: 16 }}>
          {STATIC ? (
            'Could not load prediction data. Try reloading the page.'
          ) : (
            <>
              Can’t reach the API. Start the backend with <code>uvicorn app.main:app</code> in <code>backend/</code>.
            </>
          )}
        </div>
      )}

      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </nav>

      {showLeague && (
        <div className="filters">
          <select value={league} onChange={(e) => setLeague(e.target.value)} aria-label="League">
            <option value="">All leagues</option>
            {leagues.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <main key={nonce}>
        {tab === 'Top bets' && <TopBets league={league} onLog={logBet} />}
        {tab === 'Fixtures' && <Fixtures league={league} onLog={logBet} />}
        {tab === 'Predictor' && <Predictor leagues={leagues} />}
        {tab === 'Performance' && <Performance />}
        {tab === 'Bankroll' && <BankrollPage data={bank} reload={loadBank} />}
      </main>

      {toast && (
        <div className="card small" role="status"
          style={{ position: 'fixed', bottom: 16, left: '50%', transform: 'translateX(-50%)', maxWidth: 'calc(100% - 32px)' }}>
          {toast}
        </div>
      )}

      <footer>
        Predictions are probabilistic estimates from historical data and do not guarantee outcomes. Bet responsibly,
        only with money you can afford to lose. Data: football-data.co.uk.
      </footer>
    </div>
  )
}

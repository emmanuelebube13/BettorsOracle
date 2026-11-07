// Browser-only bankroll store, used by the static (GitHub Pages) build where there is
// no server. Mirrors backend/app/bankroll.py.
import type { Bankroll, Bet } from './api'

const KEY = 'bo_bankroll_v1'
type Store = { starting: number; nextId: number; bets: Bet[] }

let memory: Store = { starting: 1000, nextId: 1, bets: [] }

function load(): Store {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) memory = JSON.parse(raw)
  } catch {
    /* storage unavailable: keep the in-memory copy */
  }
  return memory
}

function save(s: Store) {
  memory = s
  try {
    localStorage.setItem(KEY, JSON.stringify(s))
  } catch {
    /* storage unavailable */
  }
}

const now = () => new Date().toISOString().slice(0, 19) + '+00:00'

const pnl = (b: Bet) => (b.status === 'won' ? b.stake * (b.odds - 1) : b.status === 'lost' ? -b.stake : 0)
const r2 = (x: number) => Math.round(x * 100) / 100

export const localBankroll = {
  summary(): Bankroll {
    const s = load()
    const bets = [...s.bets].sort((a, b) => (b.placed_at + b.id).localeCompare(a.placed_at + a.id) || b.id - a.id)
    const settled = s.bets
      .filter((b) => b.status !== 'pending')
      .sort((a, b) => (a.settled_at ?? a.placed_at).localeCompare(b.settled_at ?? b.placed_at) || a.id - b.id)
    let balance = s.starting
    const series = [{ t: null as string | null, bankroll: r2(balance) }]
    for (const b of settled) {
      balance += pnl(b)
      series.push({ t: b.settled_at, bankroll: r2(balance) })
    }
    const pending = s.bets.filter((b) => b.status === 'pending')
    const staked = settled.filter((b) => b.status !== 'void').reduce((a, b) => a + b.stake, 0)
    const won = settled.filter((b) => b.status === 'won').length
    const decided = settled.filter((b) => b.status === 'won' || b.status === 'lost').length
    let peak = s.starting
    let maxDd = 0
    for (const p of series) {
      peak = Math.max(peak, p.bankroll)
      maxDd = Math.max(maxDd, peak ? (peak - p.bankroll) / peak : 0)
    }
    return {
      starting_bankroll: s.starting,
      bankroll: r2(balance),
      available: r2(balance - pending.reduce((a, b) => a + b.stake, 0)),
      profit: r2(balance - s.starting),
      roi: staked ? (balance - s.starting) / staked : null,
      hit_rate: decided ? won / decided : null,
      max_drawdown: maxDd,
      pending: pending.length,
      settled: settled.length,
      series,
      bets,
    }
  },
  setStarting(amount: number) {
    save({ ...load(), starting: amount })
    return this.summary()
  },
  add(b: { match: string; market: string; odds: number; stake: number }): Bet {
    const s = load()
    const bet: Bet = { id: s.nextId, placed_at: now(), status: 'pending', settled_at: null, ...b }
    save({ ...s, nextId: s.nextId + 1, bets: [...s.bets, bet] })
    return bet
  },
  settle(id: number, status: Bet['status']): Bet {
    const s = load()
    const bets = s.bets.map((b) => (b.id === id ? { ...b, status, settled_at: status === 'pending' ? null : now() } : b))
    save({ ...s, bets })
    const bet = bets.find((b) => b.id === id)
    if (!bet) throw new Error('Bet not found.')
    return bet
  },
  remove(id: number) {
    const s = load()
    save({ ...s, bets: s.bets.filter((b) => b.id !== id) })
  },
}

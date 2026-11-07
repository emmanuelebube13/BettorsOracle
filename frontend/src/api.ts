import { localBankroll } from './localBankroll'

export type Market = {
  market: string
  group: string
  prob: number
  fair_odds: number | null
  odds: number | null
  edge: number | null
  kelly_pct: number
}

export type TeamStats = Record<string, number | null>

export type Oracle = {
  pick: 'H' | 'D' | 'A'
  votes: { home: number; away: number }
  metrics: { metric: string; home: number | null; away: number | null; favours: 'home' | 'away' | null }[]
  double_chance: Record<'home' | 'away', { met: string[]; tier: 'high' | 'moderate' | 'avoid' }>
  max_criteria: number
}

export type Fixture = {
  league: string
  league_name: string
  date: string
  time: string | null
  home: string
  away: string
  enough_history: boolean
  probs: { home: number; draw: number; away: number; over25: number; btts: number }
  markets: Market[]
  oracle: Oracle
  stats: { home: TeamStats; away: TeamStats }
  h2h: { home_wins: number; away_wins: number; games: number }
}

export type TopBet = Market & {
  league: string
  league_name: string
  date: string
  time: string | null
  home: string
  away: string
  value: boolean
}

export type BetSummary = { bets: number; hit_rate: number | null; roi: number | null; profit_units: number }
export type Scores = { accuracy: number; log_loss: number; brier: number }
export type SeasonResult = {
  season: string
  matches: number
  model: Scores
  market: Scores | null
  rules_accuracy: number
  top_bets: BetSummary
  value_bets: BetSummary
  calibration: { predicted: number; actual: number; n: number }[]
}
export type Backtest = { seasons: SeasonResult[]; top_bet_threshold: number }

export type Bet = {
  id: number
  placed_at: string
  match: string
  market: string
  odds: number
  stake: number
  status: 'pending' | 'won' | 'lost' | 'void'
  settled_at: string | null
}

export type Bankroll = {
  starting_bankroll: number
  bankroll: number
  available: number
  profit: number
  roi: number | null
  hit_rate: number | null
  max_drawdown: number
  pending: number
  settled: number
  series: { t: string | null; bankroll: number }[]
  bets: Bet[]
}

export type Health = {
  status: string
  ready: boolean
  static?: boolean
  generated_at?: string
  history_updated: string | null
  fixtures_updated: string | null
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

// Static mode (GitHub Pages): read pre-computed JSON instead of calling the API.
export const STATIC = import.meta.env.VITE_STATIC === '1'

const cache = new Map<string, Promise<unknown>>()
function file<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    const p = fetch(`data/${path}`).then((r) => {
      if (!r.ok) throw new Error(`Could not load ${path} (${r.status})`)
      return r.json()
    })
    p.catch(() => cache.delete(path))
    cache.set(path, p)
  }
  return cache.get(path) as Promise<T>
}

const today = () => new Date().toISOString().slice(0, 10)

/** One pick per match: the priced market clearing minProb with the best edge (mirrors service.top_bets). */
export function topBetsFrom(fixtures: Fixture[], minProb: number): TopBet[] {
  const picks: TopBet[] = []
  for (const f of fixtures) {
    if (!f.enough_history) continue
    const cands = f.markets.filter((m) => m.prob >= minProb && m.odds)
    if (!cands.length) continue
    const m = cands.reduce((a, b) => ((b.edge ?? -1) > (a.edge ?? -1) || (b.edge === a.edge && b.prob > a.prob) ? b : a))
    picks.push({
      league: f.league, league_name: f.league_name, date: f.date, time: f.time, home: f.home, away: f.away,
      ...m, value: (m.edge ?? 0) > 0,
    })
  }
  return picks.sort((a, b) => (b.edge ?? -1) - (a.edge ?? -1) || b.prob - a.prob)
}

const staticFixtures = async (league?: string) =>
  (await file<Fixture[]>('fixtures.json')).filter((f) => f.date >= today() && (!league || f.league === league))

const staticApi = {
  health: () => file<Health>('meta.json'),
  leagues: async () => (await file<{ leagues: { code: string; name: string }[] }>('meta.json')).leagues,
  teams: () => file<Record<string, string[]>>('teams.json'),
  fixtures: staticFixtures,
  topBets: async (minProb: number, league?: string) => topBetsFrom(await staticFixtures(league), minProb),
  predict: async (home: string, away: string, league: string) => {
    const pairs = await file<Record<string, Fixture>>(`predict/${league}.json`)
    const r = pairs[`${home}|${away}`]
    if (!r) throw new Error('Unknown team(s).')
    return r
  },
  backtest: () => file<Backtest>('backtest.json'),
  refresh: async (_token?: string): Promise<unknown> => {
    throw new Error('Data refreshes automatically every 6 hours on the hosted version.')
  },
  bankroll: async () => localBankroll.summary(),
  setBankroll: async (amount: number) => localBankroll.setStarting(amount),
  addBet: async (b: { match: string; market: string; odds: number; stake: number }) => localBankroll.add(b),
  settleBet: async (id: number, status: Bet['status']) => localBankroll.settle(id, status),
  deleteBet: async (id: number) => localBankroll.remove(id),
}

const serverApi = {
  health: () => req<Health>('/api/health'),
  leagues: () => req<{ code: string; name: string }[]>('/api/leagues'),
  teams: () => req<Record<string, string[]>>('/api/teams'),
  fixtures: (league?: string) => req<Fixture[]>(`/api/fixtures${league ? `?league=${league}` : ''}`),
  topBets: (minProb: number, league?: string) =>
    req<TopBet[]>(`/api/top-bets?min_prob=${minProb}${league ? `&league=${league}` : ''}`),
  predict: (home: string, away: string, _league?: string) =>
    req<Fixture>(`/api/predict?home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}`),
  backtest: () => req<Backtest>('/api/backtest'),
  refresh: (token?: string) =>
    req<unknown>('/api/admin/refresh', { method: 'POST', headers: token ? { 'X-Admin-Token': token } : {} }),
  bankroll: () => req<Bankroll>('/api/bankroll'),
  setBankroll: (amount: number) => req<Bankroll>('/api/bankroll', { method: 'PUT', body: JSON.stringify({ amount }) }),
  addBet: (b: { match: string; market: string; odds: number; stake: number }) =>
    req<Bet>('/api/bets', { method: 'POST', body: JSON.stringify(b) }),
  settleBet: (id: number, status: Bet['status']) =>
    req<Bet>(`/api/bets/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  deleteBet: (id: number) => req<void>(`/api/bets/${id}`, { method: 'DELETE' }),
}

export const api = STATIC ? staticApi : serverApi

export const pct = (x: number | null | undefined, d = 0) => (x == null ? '–' : `${(x * 100).toFixed(d)}%`)
export const signedPct = (x: number | null | undefined, d = 1) =>
  x == null ? '–' : `${x > 0 ? '+' : ''}${(x * 100).toFixed(d)}%`
export const money = (x: number) => x.toLocaleString(undefined, { style: 'currency', currency: 'USD' })

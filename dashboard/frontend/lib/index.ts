export interface HealthStatus {
  status:        'ok' | 'stale' | 'no_data'
  timestamp:     string | null
  date:          string | null
  hours_ago:     number | null
  assets_ok:     string[]
  assets_failed: string[]
  panel_rows:    number | null
  signals_rows:  number | null
}

export interface SignalToday {
  ticker: string
  date: string
  pre_open_implied_prob: number | null
  overnight_prob_change: number | null
  pre_open_pm_volume: number | null
  pre_open_buy_ratio: number | null
  is_high_liquidity: boolean
  signal_direction: 'up' | 'down' | 'neutral' | 'unknown'
  signal_quality_score: number | null
  true_sentiment: number | null
  stock_vol_ann?: number | null
  bs_neutral_prob?: number | null
}

export interface ProbabilityPoint {
  timestamp: string
  price_up:  number | null
  volume:    number | null
  open_bet:  number | null
  high_bet:  number | null
  low_bet:   number | null
}

export interface StockPoint {
  timestamp: string
  close:     number | null
}

export interface SentimentPoint {
  timestamp:        string
  true_sentiment:   number | null
  abs_sentiment:    number | null
  bs_neutral_prob:  number | null
}

export interface AssetDetail {
  ticker:                  string
  days:                    number
  row_count:               number
  latest_signal:           SignalToday | null
  probability_series:      ProbabilityPoint[]
  stock_series:            StockPoint[]
  true_sentiment_series:   SentimentPoint[]
}

export interface HeatmapEntry {
  ticker:          string
  date:            string
  prob_direction:  1 | -1
  price_direction: 1 | -1
  prob_change:     number
  price_move:      number
  volume:          number
  quadrant:        'green' | 'red' | 'yellow' | 'gray'
}

export interface HeatmapResponse {
  days:  number
  count: number
  data:  HeatmapEntry[]
}

export type Ticker =
  | 'AAPL'
  | 'AMZN'
  | 'COIN'
  | 'GOOGL'
  | 'META'
  | 'MSFT'
  | 'NFLX'
  | 'NVDA'
  | 'PLTR'
  | 'TSLA'

export const ALL_TICKERS: Ticker[] = ['AAPL', 'AMZN', 'COIN', 'GOOGL', 'META', 'MSFT', 'NFLX', 'NVDA', 'PLTR', 'TSLA']

export interface LiveRecord {
  ticker:              string | null
  category:            string | null
  label:               string | null
  last_close:          number | null
  prev_close:          number | null
  ret_pct:             number | null
  chg_abs:             number | null
  market_cap:          number | null
  volume:              number | null
  vol_ratio:           number | null
  poly_up_probability: number | null
  poly_target_date:    string | null
  date:                string | null
  last_fetched:        string | null
  open_price:          number | null
  true_sentiment:      number | null
  bs_neutral_prob:     number | null
  sigma_live:          number | null
}

export interface LiveResponse {
  count:        number
  last_fetched: string
  data:         LiveRecord[]
}

export interface GeoMarket {
  event_id?:        string | number | null
  slug:            string
  category:        string
  display_label?:  string
  label:           string
  title?:          string
  subtitle?:       string | null
  ends:            string
  probability:     number
  prob_24h_change: number | null
  leading_outcome?: string | null
  market_type?:     'binary' | 'categorical'
  interpretation?:  string
  volume_24hr?:    number | null
  liquidity?:      number | null
  end_date?:       string | null
  tags?:           string[]
  equity_exposure: Record<string, 'HIGH' | 'MED' | 'LOW'>
  source:          'live'
}

export interface GeoResponse {
  markets:         GeoMarket[]
  macro_heat:      Record<string, Record<string, string>>
  summary:         { bullish_count: number; bearish_count: number; total_count?: number; avg_conviction: number | null }
  fetched_at?:     string
}

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: 'no-store' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `API error ${res.status} on ${path}`)
  }
  return res.json() as Promise<T>
}

export const fetchHealth = () =>
  apiFetch<HealthStatus>('/health')

export const fetchSignalsToday = () =>
  apiFetch<{ data: SignalToday[]; count: number }>('/api/signals/today')

export const fetchAsset = (ticker: string, days = 1) =>
  apiFetch<AssetDetail>(`/api/asset/${ticker}?days=${days}`)

export const fetchAssetPreopen = (ticker: string) =>
  apiFetch<{ ticker: string; preopen_series: ProbabilityPoint[] }>(`/api/asset/${ticker}/preopen`)

export const fetchHeatmap = (days = 30) =>
  apiFetch<HeatmapResponse>(`/api/heatmap?days=${days}`)

export async function fetchLive(): Promise<LiveRecord[]> {
  const base = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
  const res = await fetch(`${base}/api/live`, { cache: 'no-store' })
  if (!res.ok) return []   // covers 503 warming_up
  const json: LiveResponse = await res.json()
  return json.data ?? []
}

export async function fetchGeopolitical(): Promise<GeoResponse | null> {
  const base = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
  const res = await fetch(`${base}/api/geopolitical`, { cache: 'no-store' })
  if (!res.ok) return null
  return res.json()
}

export function retColor(ret: number | null): string {
  if (ret === null) return '#475569'
  if (ret <= -3) return '#b80f2f'
  if (ret <= -2) return '#c41e3a'
  if (ret <= -1) return '#d9435f'
  if (ret < 1)   return '#475569'
  if (ret < 2)   return '#0f766e'
  if (ret < 3)   return '#0b8f7f'
  return '#22c55e'
}

export function polyColor(prob: number | null): string {
  if (prob === null) return '#475569'
  if (prob > 0.55) return '#22c55e'
  if (prob < 0.45) return '#ef4444'
  return '#475569'
}

export function sentimentColor(ts: number | null): string {
  if (ts === null) return '#475569'
  if (ts > 0.10) return '#22c55e'
  if (ts > 0.03) return '#4ade80'
  if (ts > -0.03) return '#475569'
  if (ts > -0.10) return '#f87171'
  return '#ef4444'
}

export function diagColors(ret: number | null, prob: number | null) {
  const ul = ret === null ? '#111e2e'
    : ret > 0.1 ? '#0a3d1f' : ret < -0.1 ? '#3d0a0a' : '#1a2030'
  const lr = prob === null ? '#111e2e'
    : prob > 0.55 ? '#0a3d1f' : prob < 0.45 ? '#3d0a0a' : '#1a2030'
  return { ul, lr }
}

export function fmtRet(ret: number | null): string {
  if (ret === null) return 'N/A'
  return (ret >= 0 ? '+' : '') + ret.toFixed(2) + '%'
}

export function fmtPrice(p: number | null): string {
  if (p === null) return '—'
  if (p >= 1000) return p.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})
  if (p >= 1) return p.toFixed(2)
  return p.toFixed(4)
}

export function fmtProb(p: number | null): string {
  if (p === null) return '—'
  return Math.round(p * 100) + '%'
}

export function fmtSentiment(ts: number | null): string {
  if (ts === null) return '—'
  return (ts >= 0 ? '+' : '') + ts.toFixed(3)
}

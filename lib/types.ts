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
  ticker:                string
  date:                  string
  pre_open_implied_prob: number
  overnight_prob_change: number
  pre_open_pm_volume:    number
  pre_open_buy_ratio:    number
  is_high_liquidity:     boolean
  signal_direction:      'UP' | 'DOWN'
  signal_quality_score:  number
  true_sentiment:        number | null
}

export interface ProbabilityPoint {
  timestamp: string
  price_up:  number | null
  volume:    number | null
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

export type Ticker = 'NFLX' | 'TSLA' | 'AAPL' | 'NVDA' | 'GOOGL' | 'META' | 'MSFT' | 'AMZN'
export const ALL_TICKERS: Ticker[] = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'AMZN', 'NFLX', 'TSLA']

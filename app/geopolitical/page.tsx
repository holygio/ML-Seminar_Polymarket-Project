'use client'

import { useEffect, useMemo, useState } from 'react'
import { fetchGeopolitical, type GeoMarket, type GeoResponse } from '@/lib'


// ─── EventCard ──────────────────────────────────────────
const CATEGORY_COLORS: Record<string, { bg: string, text: string, border: string }> = {
  Rates: { bg: '#0c2a4a', text: '#38bdf8', border: '#1e3a5f' },
  Trade: { bg: '#2a1e0a', text: '#f59e0b', border: '#3a2e10' },
  Conflict: { bg: '#2a0a0a', text: '#ef4444', border: '#3a1414' },
  Politics: { bg: '#1e0a2a', text: '#a78bfa', border: '#2e1a3a' },
  Markets: { bg: '#0a2a1e', text: '#22c55e', border: '#143a2a' },
}

function EventCard({ market }: { market: GeoMarket }) {
  const palette = CATEGORY_COLORS[market.category] || CATEGORY_COLORS.Markets
  const probability = market.probability ?? 0
  const probColor =
    probability > 0.65 ? '#22c55e' :
    probability > 0.45 ? '#38bdf8' :
    probability > 0.25 ? '#f59e0b' : '#ef4444'
  const probDisplay = market.market_type === 'categorical' && market.leading_outcome
    ? `${Math.round(probability * 100)}% -> "${market.leading_outcome}"`
    : `${Math.round(probability * 100)}%`
  const showTrend = market.prob_24h_change !== null && Math.abs(market.prob_24h_change ?? 0) >= 0.01
  const trendText = showTrend
    ? `${(market.prob_24h_change ?? 0) > 0 ? '▲' : '▼'} ${Math.abs(Math.round((market.prob_24h_change ?? 0) * 1000) / 10)}pp 24h`
    : null
  const trendColor = (market.prob_24h_change ?? 0) > 0 ? '#22c55e' : '#ef4444'
  const highVol = (market.volume_24hr ?? 0) > 50_000
  const volText = market.volume_24hr
    ? market.volume_24hr > 1_000_000
      ? `$${(market.volume_24hr / 1_000_000).toFixed(1)}M vol`
      : `$${(market.volume_24hr / 1_000).toFixed(0)}K vol`
    : null
  const exposureEntries = Object.entries(market.equity_exposure)

  return (
    <div 
      style={{
        background: '#0a1628',
        border: '1px solid #1a2840',
        borderRadius: '4px',
        padding: '11px 12px',
        cursor: 'pointer'
      }}
      onMouseEnter={(e) => e.currentTarget.style.borderColor = '#1e3a5f'}
      onMouseLeave={(e) => e.currentTarget.style.borderColor = '#1a2840'}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{
            background: palette.bg,
            color: palette.text,
            border: `1px solid ${palette.border}`,
            borderRadius: '2px',
            padding: '2px 7px',
            fontSize: '9px',
            letterSpacing: '1px',
            textTransform: 'uppercase',
            fontFamily: '"Courier New", monospace'
          }}>
            {market.category}
          </div>
          {highVol && volText && (
            <div style={{
              background: '#10321e',
              color: '#4ade80',
              border: '1px solid #184c2f',
              borderRadius: '2px',
              padding: '2px 7px',
              fontSize: '9px',
              fontFamily: '"Courier New", monospace'
            }}>
              {volText}
            </div>
          )}
        </div>
        <div style={{ textAlign: 'right', minWidth: '82px' }}>
          <div style={{ fontSize: '9px', color: '#334155', letterSpacing: '0.5px' }}>
            ends {market.ends}
          </div>
          {trendText && (
            <div style={{
              fontSize: '10px',
              marginTop: '2px',
              color: trendColor
            }}>
              {trendText}
            </div>
          )}
        </div>
      </div>

      <div style={{ fontSize: '18px', color: '#f8fafc', lineHeight: 1.35, marginBottom: '8px' }}>
        {market.display_label || market.label}
      </div>

      {market.interpretation && (
        <div style={{ fontSize: '11px', color: '#7c8ea6', lineHeight: 1.5, marginBottom: '12px' }}>
          {market.interpretation}
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div style={{ flex: 1, height: '5px', background: '#122235', borderRadius: '999px' }}>
          <div style={{
            width: `${probability * 100}%`,
            background: probColor,
            height: '100%',
            borderRadius: '999px'
          }} />
        </div>
        <div style={{ fontSize: '13px', fontFamily: '"Courier New", monospace', color: probColor, whiteSpace: 'nowrap' }}>
          {probDisplay}
        </div>
      </div>

      <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid #111e2e' }}>
        <div style={{ fontSize: '9px', color: '#334155', letterSpacing: '1px', textTransform: 'uppercase' }}>
          Equity exposure
        </div>
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '4px' }}>
          {exposureEntries.length === 0 && (
            <div style={{
              color: '#64748b',
              fontSize: '9px',
              fontFamily: '"Courier New", monospace',
              letterSpacing: '0.5px'
            }}>
              no direct equity match
            </div>
          )}
          {exposureEntries.map(([ticker, level]) => {
            const isHi = level === 'HIGH'
            const isMd = level === 'MED'
            return (
              <div key={ticker} style={{
                background: isHi ? '#1a2e1a' : isMd ? '#2a2010' : '#1e1e2a',
                color: isHi ? '#4ade80' : isMd ? '#fbbf24' : '#64748b',
                border: `1px solid ${isHi ? '#1e3d1e' : isMd ? '#3a2e10' : '#252535'}`,
                padding: '2px 6px',
                borderRadius: '2px',
                fontSize: '9px',
                fontFamily: '"Courier New", monospace',
                letterSpacing: '0.5px'
              }}>
                {ticker} {level.toLowerCase()}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ─── MacroHeatGrid ──────────────────────────────────────────
function MacroHeatGrid({ heat }: { heat: Record<string, Record<string, string>> }) {
const TICKERS = ['NVDA', 'AAPL', 'MSFT', 'AMZN', 'TSLA', 'GOOGL', 'META', 'NFLX', 'PLTR', 'COIN']
  
  return (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ minWidth: '320px' }}>
        <div style={{ display: 'flex', gap: '4px', marginBottom: '3px', paddingLeft: '42px' }}>
          {['RATES', 'TRADE', 'MKT', 'CONF', 'POL'].map(col => (
            <div key={col} style={{ fontSize: '8px', color: '#334155', width: '22px', textAlign: 'center', letterSpacing: '0.5px' }}>
              {col}
            </div>
          ))}
        </div>
        {TICKERS.map(ticker => {
          const levels = heat[ticker] || {}
          return (
            <div key={ticker} style={{ display: 'flex', gap: '4px', alignItems: 'center', marginTop: '6px' }}>
              <div style={{ 
                fontSize: '9px', color: '#334155', width: '38px', textAlign: 'right', 
                letterSpacing: '0.5px', fontFamily: '"Courier New", monospace' 
              }}>
                {ticker}
              </div>
              {['Rates', 'Trade', 'Markets', 'Conflict', 'Politics'].map(k => {
                const val = levels[k] || 'NEUTRAL'
                const isHi = val === 'HIGH'
                const isMd = val === 'MED'
                const isLo = val === 'LOW'
                return (
                  <div key={k} style={{
                    width: '22px', height: '22px', borderRadius: '2px', 
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '7px',
                    background: isHi ? '#14532d' : isMd ? '#2a2010' : isLo ? '#1a1a2e' : '#1e2d3d',
                    color: isHi ? '#4ade80' : isMd ? '#fbbf24' : isLo ? '#3b3b5c' : '#334155'
                  }}>
                    {isHi ? 'HI' : isMd ? 'MD' : isLo ? 'LO' : '—'}
                  </div>
                )
              })}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── MacroMovers ──────────────────────────────────────────
function MacroMovers({ markets }: { markets: GeoMarket[] }) {
  const movers = markets
    .filter(market => market.prob_24h_change !== null && Object.keys(market.equity_exposure ?? {}).length > 0)
    .sort((a, b) => Math.abs(b.prob_24h_change ?? 0) - Math.abs(a.prob_24h_change ?? 0))
    .slice(0, 4)

  if (movers.length === 0) {
    return (
      <div style={{ marginTop: '24px' }}>
        <div style={{ fontSize: '11px', color: '#cbd5e1', marginBottom: '8px', letterSpacing: '0.5px' }}>
          Today&apos;s Macro-Driven Movers
        </div>
        <div style={{ fontSize: '10px', color: '#64748b', fontFamily: '"Courier New", monospace' }}>
          No live mover with mapped equity exposure is available yet.
        </div>
      </div>
    )
  }

  return (
    <div style={{ marginTop: '24px' }}>
      <div style={{ fontSize: '11px', color: '#cbd5e1', marginBottom: '8px', letterSpacing: '0.5px' }}>
        Today&apos;s Macro-Driven Movers
      </div>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {movers.map(market => {
          const change = market.prob_24h_change ?? 0
          const exposureTickers = Object.keys(market.equity_exposure ?? {})
          const leadTicker = exposureTickers[0] ?? 'MACRO'
          const isPos = change >= 0
          return (
            <div
              key={market.slug}
              style={{
                background: '#0a1628',
                border: `1px solid ${isPos ? '#1e3d1e' : '#3d1e1e'}`,
                borderRadius: '4px',
                padding: '6px 10px',
                display: 'flex',
                gap: '6px',
                alignItems: 'center',
              }}
            >
              <span style={{ fontSize: '11px', color: '#f8fafc', fontWeight: 600, fontFamily: '"Courier New", monospace' }}>
                {leadTicker}
              </span>
              <span style={{ fontSize: '10px', color: isPos ? '#4ade80' : '#ef4444' }}>
                {isPos ? '+' : ''}{(change * 100).toFixed(1)}pp
              </span>
              <span style={{ fontSize: '9px', color: '#64748b', marginLeft: '4px' }}>
                via {market.category}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── SummaryCards ──────────────────────────────────────────
function Card({ title, value, sub, color }: { title: string, value: string | number, sub: string, color: string }) {
  return (
    <div style={{ background: '#0a1628', border: '1px solid #1a2840', borderRadius: '4px', padding: '8px 10px' }}>
      <div style={{ fontSize: '9px', color: '#334155', textTransform: 'uppercase', letterSpacing: '1px' }}>{title}</div>
      <div style={{ fontSize: '18px', fontWeight: 500, fontFamily: '"Courier New", monospace', marginTop: '4px', color }}>{value}</div>
      <div style={{ fontSize: '9px', marginTop: '2px', color: '#475569' }}>{sub}</div>
    </div>
  )
}

function SummaryCards({ summary }: { summary: GeoResponse['summary'] }) {
  const avgConviction = summary.avg_conviction === null
    ? '—'
    : `${Math.round(summary.avg_conviction * 100)}%`

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px' }}>
      <Card 
        title="Bullish events" 
        value={summary.bullish_count} 
        sub="prob > 55%" 
        color="#22c55e" 
      />
      <Card 
        title="Bearish events" 
        value={summary.bearish_count} 
        sub="prob < 45%" 
        color="#ef4444" 
      />
      <Card 
        title="Avg conviction" 
        value={avgConviction} 
        sub="across all markets" 
        color="#f8fafc" 
      />
    </div>
  )
}

const FILTERS = ['All', 'Rates', 'Trade', 'Markets', 'Conflict', 'Politics'] as const
const CATEGORY_DISPLAY_ORDER = ['Rates', 'Trade', 'Markets', 'Conflict', 'Politics'] as const
const CATEGORY_LABELS: Record<string, string> = {
  Rates: 'Central banks & rates',
  Trade: 'Trade & tariffs',
  Markets: 'Markets & assets',
  Conflict: 'Conflicts & geopolitics',
  Politics: 'Political risk',
}
const CATEGORY_DOTS: Record<string, string> = {
  Rates: '#38bdf8',
  Trade: '#f59e0b',
  Markets: '#22c55e',
  Conflict: '#ef4444',
  Politics: '#a78bfa',
}

function SectionHeader({ category, count }: { category: string, count: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: CATEGORY_DOTS[category] || '#64748b' }} />
        <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '2px', fontFamily: '"Courier New", monospace' }}>
          {CATEGORY_LABELS[category] || category}
        </div>
      </div>
      <div style={{ fontSize: '9px', color: '#334155', fontFamily: '"Courier New", monospace' }}>
        {count} markets
      </div>
    </div>
  )
}

export default function GeopoliticalPage() {
  const [data, setData] = useState<GeoResponse | null>(null)
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('All')

  useEffect(() => {
    let mounted = true

    const load = async () => {
      const res = await fetchGeopolitical()
      if (mounted && res) {
        setData(res)
      }
    }

    load()
    const interval = setInterval(load, 60_000)
    return () => {
      mounted = false
      clearInterval(interval)
    }
  }, [])

  const filteredMarkets = useMemo(() => {
    if (!data) return []
    if (filter === 'All') return data.markets
    return data.markets.filter(market => market.category === filter)
  }, [data, filter])

  const grouped = useMemo(() => {
    return CATEGORY_DISPLAY_ORDER.reduce((acc, category) => {
      const markets = filteredMarkets.filter(market => market.category === category)
      if (markets.length > 0) {
        acc[category] = markets
      }
      return acc
    }, {} as Record<string, GeoMarket[]>)
  }, [filteredMarkets])

  const topPulse = useMemo(() => {
    return filteredMarkets
      .slice()
      .sort((a, b) => (b.volume_24hr ?? 0) - (a.volume_24hr ?? 0))
      .slice(0, 5)
  }, [filteredMarkets])

  const activeSignal = filteredMarkets
    .filter(market => market.prob_24h_change !== null)
    .sort((a, b) => Math.abs(b.prob_24h_change ?? 0) - Math.abs(a.prob_24h_change ?? 0))[0] ?? filteredMarkets[0] ?? null

  if (!data) {
    return <div style={{ color: '#fff', padding: '20px' }}>Loading prediction data...</div>
  }

  return (
    <div style={{ maxWidth: '1240px', margin: '0 auto', padding: '32px', color: '#e2e8f0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '24px', marginBottom: '28px' }}>
        <div>
          <h1 style={{ fontSize: '28px', color: '#f8fafc', margin: '0 0 8px 0', fontFamily: '"Courier New", monospace', fontWeight: 400 }}>
            Geopolitical pulse
          </h1>
          <div style={{ fontSize: '12px', color: '#475569', letterSpacing: '1.2px', fontFamily: '"Courier New", monospace', textTransform: 'uppercase' }}>
            Crowd-predicted macro events · equity exposure mapped
          </div>
        </div>

        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {FILTERS.map(item => {
            const active = filter === item
            return (
              <button
                key={item}
                onClick={() => setFilter(item)}
                style={{
                  padding: '7px 14px',
                  borderRadius: '2px',
                  fontSize: '11px',
                  fontFamily: '"Courier New", monospace',
                  letterSpacing: '1px',
                  textTransform: 'uppercase',
                  cursor: 'pointer',
                  background: active ? '#12304d' : 'transparent',
                  color: active ? '#60a5fa' : '#64748b',
                  border: active ? '1px solid #2563eb' : '1px solid #1e293b',
                }}
              >
                {item}
              </button>
            )
          })}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.15fr) minmax(320px, 0.85fr)', gap: '20px' }}>
        <div>
          {CATEGORY_DISPLAY_ORDER.map(category => {
            const markets = grouped[category]
            if (!markets || markets.length === 0) return null
            return (
              <section key={category} style={{ marginBottom: '22px' }}>
                <SectionHeader category={category} count={markets.length} />
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {markets.map(market => (
                    <EventCard key={market.slug} market={market} />
                  ))}
                </div>
              </section>
            )
          })}
        </div>

        <div>
          <div style={{ background: '#0a1628', border: '1px solid #162335', borderRadius: '6px', padding: '14px', marginBottom: '16px' }}>
            <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '2px', fontFamily: '"Courier New", monospace', marginBottom: '10px' }}>
              Macro signal summary
            </div>
            <SummaryCards summary={data.summary} />
          </div>

          <div style={{ background: '#0a1628', border: '1px solid #162335', borderRadius: '6px', padding: '14px', marginBottom: '16px' }}>
            <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '2px', fontFamily: '"Courier New", monospace', marginBottom: '10px' }}>
              Key market pulse
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {topPulse.map(market => {
                const probability = market.probability ?? 0
                const width = `${Math.round(probability * 100)}%`
                const barColor =
                  probability > 0.65 ? '#22c55e' :
                  probability > 0.45 ? '#38bdf8' :
                  probability > 0.25 ? '#f59e0b' : '#ef4444'
                return (
                  <div key={market.slug} style={{ border: '1px solid #162335', borderRadius: '4px', padding: '8px 10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', marginBottom: '6px' }}>
                      <div style={{ fontSize: '12px', color: '#dbe5f0', lineHeight: 1.3 }}>
                        {market.display_label || market.label}
                      </div>
                      <div style={{ fontSize: '12px', color: barColor, fontFamily: '"Courier New", monospace', whiteSpace: 'nowrap' }}>
                        {Math.round(probability * 100)}%
                      </div>
                    </div>
                    <div style={{ height: '4px', background: '#122235', borderRadius: '999px', overflow: 'hidden' }}>
                      <div style={{ width, height: '100%', background: barColor }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          <div style={{ background: '#0a1628', border: '1px solid #162335', borderRadius: '6px', padding: '14px', marginBottom: '16px' }}>
            <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '2px', fontFamily: '"Courier New", monospace', marginBottom: '10px' }}>
              Equity macro-exposure heat
            </div>
            <MacroHeatGrid heat={data.macro_heat} />
          </div>

          <div style={{ background: '#0a1628', border: '1px solid #162335', borderRadius: '6px', padding: '14px', marginBottom: '16px' }}>
            <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '2px', fontFamily: '"Courier New", monospace', marginBottom: '8px' }}>
              Active signal
            </div>
            <div style={{ fontSize: '13px', color: '#cbd5e1', lineHeight: 1.6 }}>
              {activeSignal?.interpretation || 'No live macro signal is available yet.'}
            </div>
          </div>

          <MacroMovers markets={filteredMarkets} />
        </div>
      </div>
    </div>
  )
}

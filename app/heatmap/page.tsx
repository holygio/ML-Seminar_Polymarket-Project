'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { fetchHeatmap, type HeatmapEntry } from '@/lib'


// ─── AlignmentGrid ──────────────────────────────────────────
interface AlignmentGridProps {
  data: HeatmapEntry[]
}

const TICKERS = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'AMZN', 'NFLX', 'TSLA']

const QUADRANT_COLOR: Record<string, string> = {
  green: '#10b981',
  red: '#ef4444',
  yellow: '#f59e0b',
  gray: '#374151',
}

function AlignmentGrid({ data }: AlignmentGridProps) {
  const router = useRouter()
  const allDates = [...new Set(data.map(d => d.date))].sort()
  const lookup = new Map<string, HeatmapEntry>(data.map(d => [`${d.ticker}|${d.date}`, d]))

  if (allDates.length === 0) {
    return (
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '40px',
        textAlign: 'center',
        color: 'var(--text-muted)',
        fontSize: '13px',
      }}>
        No alignment data available for this time period.
        Run the pipeline to generate data.
      </div>
    )
  }

  const fmt = (iso: string) => {
    const [, m, day] = iso.split('-')
    return `${m}/${day}`
  }

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: '8px',
      padding: '16px',
      overflowX: 'auto',
    }}>
      <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: '600px' }}>
        <thead>
          <tr>
            <th style={{
              width: '64px',
              textAlign: 'left',
              fontSize: '11px',
              color: 'var(--text-muted)',
              padding: '0 8px 8px',
              fontWeight: 400,
            }}>
              ASSET
            </th>
            {allDates.map(d => (
              <th
                key={d}
                style={{
                  fontSize: '10px',
                  color: 'var(--text-muted)',
                  fontWeight: 400,
                  padding: '0 2px 8px',
                  textAlign: 'center',
                  minWidth: '28px',
                }}
              >
                {fmt(d)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {TICKERS.map(ticker => (
            <tr key={ticker}>
              <td
                onClick={() => router.push(`/asset/${ticker}`)}
                style={{
                  fontSize: '12px',
                  fontWeight: 700,
                  padding: '3px 8px 3px 0',
                  cursor: 'pointer',
                  color: 'var(--accent)',
                }}
              >
                {ticker}
              </td>
              {allDates.map(date => {
                const entry = lookup.get(`${ticker}|${date}`)
                const bg = entry ? QUADRANT_COLOR[entry.quadrant] : 'var(--bg)'
                const op = entry ? 0.75 : 0.15
                const title = entry
                  ? `${entry.ticker} — ${entry.date}\nPM change: ${(entry.prob_change * 100).toFixed(1)}%\nPrice move: ${(entry.price_move * 100).toFixed(2)}%\nVolume: $${entry.volume.toFixed(0)}\nQuadrant: ${entry.quadrant}`
                  : 'No data'

                return (
                  <td key={date} title={title} style={{ textAlign: 'center' }}>
                    <div
                      style={{
                        width: '22px',
                        height: '22px',
                        borderRadius: '3px',
                        background: bg,
                        opacity: op,
                        margin: '2px auto',
                      }}
                    />
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── AlignmentSummaryStats ──────────────────────────────────────────
interface AlignmentSummaryStatsProps {
  data: HeatmapEntry[]
}

function AlignmentSummaryStats({ data }: AlignmentSummaryStatsProps) {
  if (data.length === 0) return null

  const alignedQuadrants = new Set(['green', 'red'])
  const nonGray = data.filter(item => item.quadrant !== 'gray')
  const aligned = nonGray.filter(item => alignedQuadrants.has(item.quadrant))
  const highLiquidity = data.filter(item => item.volume >= 500)
  const highLiquidityDirectional = highLiquidity.filter(item => item.quadrant !== 'gray')
  const highLiquidityAligned = highLiquidityDirectional.filter(item => alignedQuadrants.has(item.quadrant))

  const overallRate = nonGray.length > 0 ? aligned.length / nonGray.length : 0
  const highLiquidityRate = highLiquidityDirectional.length > 0
    ? highLiquidityAligned.length / highLiquidityDirectional.length
    : 0

  const grouped = groupByTicker(nonGray)
  let bestTicker = '—'
  let bestRate = 0
  let worstTicker = '—'
  let worstRate = 0
  let first = true

  for (const [ticker, entries] of Object.entries(grouped)) {
    if (entries.length === 0) continue
    const rate = entries.filter(item => alignedQuadrants.has(item.quadrant)).length / entries.length
    if (first || rate > bestRate) {
      bestTicker = ticker
      bestRate = rate
    }
    if (first || rate < worstRate) {
      worstTicker = ticker
      worstRate = rate
    }
    first = false
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
      <StatCard
        label="Overall Alignment"
        value={`${Math.round(overallRate * 100)}%`}
        sub={`${aligned.length} of ${nonGray.length} directional signals`}
      />
      <StatCard
        label="High-Liq Alignment"
        value={`${Math.round(highLiquidityRate * 100)}%`}
        sub={`volume > $500 only (${highLiquidityDirectional.length} obs)`}
        highlight
      />
      <StatCard
        label="Best Asset"
        value={bestTicker}
        sub={`${Math.round(bestRate * 100)}% alignment rate`}
        valueColor="var(--green)"
      />
      <StatCard
        label="Worst Asset"
        value={worstTicker}
        sub={`${Math.round(worstRate * 100)}% alignment rate`}
        valueColor="var(--red)"
      />
    </div>
  )
}

function StatCard({
  label,
  value,
  sub,
  highlight = false,
  valueColor,
}: {
  label: string
  value: string
  sub: string
  highlight?: boolean
  valueColor?: string
}) {
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: `1px solid ${highlight ? 'var(--accent)' : 'var(--border)'}`,
      borderRadius: '8px',
      padding: '16px',
    }}>
      <div style={{
        fontSize: '11px',
        color: 'var(--text-muted)',
        fontWeight: 600,
        textTransform: 'uppercase',
      }}>
        {label}
      </div>
      <div style={{
        fontSize: '24px',
        fontWeight: 800,
        fontFamily: 'var(--mono)',
        color: valueColor ?? 'var(--text)',
      }}>
        {value}
      </div>
      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
        {sub}
      </div>
    </div>
  )
}

function groupByTicker(data: HeatmapEntry[]) {
  return data.reduce<Record<string, HeatmapEntry[]>>((acc, item) => {
    if (!acc[item.ticker]) acc[item.ticker] = []
    acc[item.ticker].push(item)
    return acc
  }, {})
}

// ─── QuadrantLegend ──────────────────────────────────────────
const QUADRANTS = [
  { color: '#10b981', label: 'Aligned Bullish', desc: 'Prob ↑ & Price ↑' },
  { color: '#ef4444', label: 'Aligned Bearish', desc: 'Prob ↓ & Price ↓' },
  { color: '#f59e0b', label: 'Divergent', desc: 'Prob and price disagree' },
  { color: '#374151', label: 'No Signal', desc: 'Low volume or small move' },
]

function QuadrantLegend() {
  return (
    <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
      {QUADRANTS.map(item => (
        <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '12px',
            height: '12px',
            borderRadius: '2px',
            background: item.color,
          }} />
          <div>
            <span style={{ fontSize: '12px', fontWeight: 600 }}>{item.label}</span>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '6px' }}>
              {item.desc}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── TimeFilterBar ──────────────────────────────────────────
interface TimeFilterBarProps {
  selected: number
  onChange: (days: number) => void
}

const OPTIONS = [
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
  { label: '60D', days: 60 },
]

function TimeFilterBar({ selected, onChange }: TimeFilterBarProps) {
  return (
    <div style={{ display: 'flex', gap: '4px' }}>
      {OPTIONS.map(opt => (
        <button
          key={opt.days}
          onClick={() => onChange(opt.days)}
          style={{
            padding: '6px 14px',
            borderRadius: '5px',
            border: '1px solid var(--border)',
            background: selected === opt.days ? 'var(--accent)' : 'var(--bg-card)',
            color: selected === opt.days ? 'white' : 'var(--text-muted)',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

export default function HeatmapPage() {
  const [days, setDays] = useState(30)
  const [data, setData] = useState<HeatmapEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchHeatmap(days)
      .then(res => setData(res.data))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [days])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: '16px',
        flexWrap: 'wrap',
      }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '4px' }}>
            Signal Alignment Heatmap
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Did Polymarket probability direction match stock price direction?
          </p>
        </div>
        <TimeFilterBar selected={days} onChange={setDays} />
      </div>

      <QuadrantLegend />

      {loading && (
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          height: '320px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-muted)',
          fontSize: '13px',
        }}>
          Loading heatmap...
        </div>
      )}

      {error && (
        <div style={{
          background: 'var(--red-dim)',
          border: '1px solid var(--red)',
          borderRadius: '6px',
          padding: '12px 16px',
          color: 'var(--red)',
          fontSize: '13px',
        }}>
          {error}
        </div>
      )}

      {!loading && !error && (
        <>
          <AlignmentGrid data={data} />
          <AlignmentSummaryStats data={data} />
        </>
      )}
    </div>
  )
}

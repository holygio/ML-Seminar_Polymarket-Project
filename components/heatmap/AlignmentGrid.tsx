'use client'

import { useRouter } from 'next/navigation'
import type { HeatmapEntry } from '@/lib/types'

interface Props {
  data: HeatmapEntry[]
}

const TICKERS = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'AMZN', 'NFLX', 'TSLA']

const QUADRANT_COLOR: Record<string, string> = {
  green: '#10b981',
  red: '#ef4444',
  yellow: '#f59e0b',
  gray: '#374151',
}

export default function AlignmentGrid({ data }: Props) {
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

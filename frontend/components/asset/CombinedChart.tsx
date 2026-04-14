'use client'

import { useMemo } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ProbabilityPoint, StockPoint } from '@/lib'

interface Props {
  days: number
  stock: StockPoint[]
  prob: ProbabilityPoint[]
}

function formatAxisLabel(value: string) {
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value.slice(5, 10)
  return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function formatTimeLabel(value: string) {
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}

function buildSeries<T extends { timestamp: string }>(
  rows: T[],
  extractor: (row: T) => number | null,
  days: number,
) {
  if (days === 1) {
    return rows.map(row => ({
      x: row.timestamp,
      label: formatTimeLabel(row.timestamp),
      value: extractor(row),
    }))
  }

  const byDay = new Map<string, { x: string; label: string; value: number | null }>()
  rows.forEach(row => {
    const day = row.timestamp.slice(0, 10)
    byDay.set(day, {
      x: day,
      label: formatAxisLabel(day),
      value: extractor(row),
    })
  })

  return Array.from(byDay.values()).sort((a, b) => a.x.localeCompare(b.x))
}

export default function CombinedChart({ days, stock, prob }: Props) {
  const stockSeries = useMemo(
    () => buildSeries(stock, row => row.close, days),
    [stock, days],
  )

  const probSeries = useMemo(
    () => buildSeries(prob, row => (row.price_up !== null ? row.price_up * 100 : null), days),
    [prob, days],
  )

  const latestPrice = stockSeries.length > 0 ? stockSeries[stockSeries.length - 1].value : null
  const rangeLabel = days === 1 ? '1D' : `${days}D`

  return (
    <div style={{ marginBottom: '32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '24px' }}>
        <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#0ea5e9' }} />
        <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '2px', fontFamily: '"Courier New", monospace' }}>
          PRICE + POLYMARKET PROBABILITY · {rangeLabel}
        </div>
      </div>

      <div style={{ marginBottom: '28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '10px' }}>
          <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '1.5px', fontFamily: '"Courier New", monospace' }}>
            Stock price
          </div>
          <div style={{ fontSize: '12px', color: '#cbd5e1', fontFamily: '"Courier New", monospace' }}>
            {latestPrice !== null ? `$${latestPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
          </div>
        </div>

        <div style={{ height: '280px', width: '100%' }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={stockSeries}>
              <defs>
                <linearGradient id="assetPriceFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#60a5fa" stopOpacity={0.24} />
                  <stop offset="95%" stopColor="#60a5fa" stopOpacity={0.04} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#132235" strokeDasharray="3 3" />
              <XAxis dataKey="label" stroke="#334155" fontSize={9} tickMargin={10} minTickGap={18} axisLine={false} tickLine={false} tick={{ fill: '#64748b' }} />
              <YAxis
                stroke="#334155"
                fontSize={9}
                domain={['auto', 'auto']}
                tickFormatter={(value) => `$${Number(value).toFixed(0)}`}
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#64748b' }}
                orientation="right"
              />
              <Tooltip
                formatter={(value) => {
                  const numeric = typeof value === 'number' ? value : null
                  return numeric === null ? '—' : `$${numeric.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                }}
                labelFormatter={(label) => `${days === 1 ? 'Time' : 'Date'} ${label}`}
                contentStyle={{ background: '#0a1628', border: '1px solid #1a2840', color: '#e2e8f0' }}
              />
              <Area type="monotone" dataKey="value" stroke="#60a5fa" strokeWidth={2} fill="url(#assetPriceFill)" connectNulls />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '10px' }}>
          <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '1.5px', fontFamily: '"Courier New", monospace' }}>
            Polymarket probability
          </div>
          <div style={{ fontSize: '12px', color: '#38bdf8', fontFamily: '"Courier New", monospace' }}>
            {probSeries.length > 0 && probSeries[probSeries.length - 1].value !== null
              ? `${Number(probSeries[probSeries.length - 1].value).toFixed(1)}%`
              : '—'}
          </div>
        </div>

        <div style={{ height: '190px', width: '100%' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={probSeries}>
              <CartesianGrid stroke="#132235" strokeDasharray="3 3" />
              <XAxis dataKey="label" stroke="#334155" fontSize={9} tickMargin={10} minTickGap={18} axisLine={false} tickLine={false} tick={{ fill: '#64748b' }} />
              <YAxis
                stroke="#334155"
                fontSize={9}
                domain={[0, 100]}
                tickFormatter={(value) => `${Math.round(Number(value))}%`}
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#64748b' }}
                orientation="right"
              />
              <Tooltip
                formatter={(value) => {
                  const numeric = typeof value === 'number' ? value : null
                  return numeric === null ? '—' : `${numeric.toFixed(1)}%`
                }}
                labelFormatter={(label) => `${days === 1 ? 'Time' : 'Date'} ${label}`}
                contentStyle={{ background: '#0a1628', border: '1px solid #1a2840', color: '#e2e8f0' }}
              />
              <Line type="monotone" dataKey="value" stroke="#38bdf8" strokeWidth={2} dot={days === 1 ? false : { r: 2 }} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

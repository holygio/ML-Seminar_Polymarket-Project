'use client'

import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ProbabilityPoint } from '@/lib/types'

interface Props {
  data: ProbabilityPoint[]
  preopenData?: ProbabilityPoint[]
}

export default function ProbabilityChart({ data, preopenData }: Props) {
  const fullData = [...(preopenData ?? []), ...data].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  )

  const chartData = fullData
    .filter(point => point.timestamp)
    .map(point => ({
      ...point,
      ts: new Date(point.timestamp).getTime(),
      priceUpPct: point.price_up != null ? point.price_up * 100 : null,
    }))

  if (chartData.length === 0) {
    return (
      <ChartShell title="PM Probability">
        <EmptyState message="No probability data available" />
      </ChartShell>
    )
  }

  const { midnightRef, marketOpenRef, marketCloseRef } = findReferenceTimes(chartData)
  const domainValues = chartData.map(point => point.ts)
  for (const value of [midnightRef, marketOpenRef, marketCloseRef]) {
    if (value != null) domainValues.push(value)
  }
  const xDomain: [number, number] = [Math.min(...domainValues), Math.max(...domainValues)]

  return (
    <ChartShell title="PM Probability">
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <defs>
            <linearGradient id="probabilityFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="#2a3448" />

          <XAxis
            dataKey="ts"
            domain={xDomain}
            tickFormatter={formatTime}
            tick={{ fontSize: 10, fill: '#6b7a8d' }}
            tickLine={false}
            axisLine={{ stroke: '#2a3448' }}
            type="number"
            scale="time"
          />

          <YAxis
            yAxisId="prob"
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: '#6b7a8d' }}
            tickFormatter={value => `${value}%`}
            tickLine={false}
            axisLine={false}
          />

          <YAxis
            yAxisId="vol"
            orientation="right"
            domain={[0, (dataMax: number) => dataMax * 6]}
            tick={{ fontSize: 10, fill: '#6b7a8d' }}
            tickFormatter={formatVolumeTick}
            tickLine={false}
            axisLine={false}
          />

          <ReferenceLine
            yAxisId="prob"
            y={50}
            stroke="#4a5568"
            strokeDasharray="4 4"
          />

          {midnightRef != null && (
            <ReferenceLine
              yAxisId="prob"
              x={midnightRef}
              stroke="#6b7a8d"
              strokeDasharray="3 4"
              label={{ value: '00:00', fill: '#6b7a8d', fontSize: 9, position: 'insideTopRight' }}
            />
          )}

          {marketOpenRef != null && (
            <ReferenceLine
              yAxisId="prob"
              x={marketOpenRef}
              stroke="#ef4444"
              strokeWidth={1.5}
              label={{ value: 'Market Open', fill: '#ef4444', fontSize: 9, position: 'insideTopRight' }}
            />
          )}

          {marketCloseRef != null && (
            <ReferenceLine
              yAxisId="prob"
              x={marketCloseRef}
              stroke="#f59e0b"
              strokeWidth={1.5}
              label={{ value: 'Market Close', fill: '#f59e0b', fontSize: 9, position: 'insideTopRight' }}
            />
          )}

          <Bar
            yAxisId="vol"
            dataKey="volume"
            fill="#4a5568"
            opacity={0.12}
            radius={[2, 2, 0, 0]}
            isAnimationActive={false}
          />

          <Area
            yAxisId="prob"
            type="monotone"
            dataKey="priceUpPct"
            stroke="#10b981"
            strokeWidth={2}
            fill="url(#probabilityFill)"
            dot={false}
            activeDot={{ r: 3 }}
            connectNulls
            isAnimationActive={false}
          />

          <Tooltip
            contentStyle={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              fontSize: '12px',
            }}
            formatter={(value, name) => {
              const numericValue = typeof value === 'number' ? value : null
              const label = typeof name === 'string' ? name : String(name)
              if (label === 'priceUpPct') {
                return [numericValue == null ? '—' : `${numericValue.toFixed(1)}%`, 'PM Probability']
              }
              if (label === 'volume') {
                return [numericValue == null ? '—' : `$${Math.round(numericValue).toLocaleString()}`, 'Volume']
              }
              return [numericValue == null ? '—' : numericValue, label]
            }}
            labelFormatter={value => formatTooltipTime(Number(value))}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

function findReferenceTimes(data: Array<{ ts: number }>) {
  let midnightRef: number | null = null
  let marketOpenRef: number | null = null
  let marketCloseRef: number | null = null

  for (const point of data) {
    const parts = getNyParts(point.ts)
    if (midnightRef == null && parts.hour === 0 && parts.minute === 0) midnightRef = point.ts
    if (marketOpenRef == null && parts.hour === 9 && parts.minute === 30) marketOpenRef = point.ts
    if (marketCloseRef == null && parts.hour === 16 && parts.minute === 0) marketCloseRef = point.ts
  }

  if (marketOpenRef == null && data.length > 0) marketOpenRef = data[0].ts
  if (marketCloseRef == null && data.length > 0) marketCloseRef = data[data.length - 1].ts
  if (midnightRef == null && marketOpenRef != null) midnightRef = marketOpenRef - (9.5 * 60 * 60 * 1000)

  return { midnightRef, marketOpenRef, marketCloseRef }
}

function getNyParts(timestamp: number) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(new Date(timestamp))

  const read = (type: string) => parts.find(part => part.type === type)?.value ?? '00'
  return {
    year: Number(read('year')),
    month: Number(read('month')),
    day: Number(read('day')),
    hour: Number(read('hour')),
    minute: Number(read('minute')),
  }
}

function formatTime(value: number) {
  return new Date(value).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'America/New_York',
  })
}

function formatTooltipTime(value: number) {
  return new Date(value).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'America/New_York',
  }) + ' ET'
}

function formatVolumeTick(value: number) {
  if (value >= 1000) return `$${(value / 1000).toFixed(1)}k`
  return `$${Math.round(value)}`
}

function ChartShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: '8px',
      padding: '16px',
    }}>
      <div style={{
        fontSize: '12px',
        color: 'var(--text-muted)',
        marginBottom: '12px',
        fontWeight: 600,
        letterSpacing: '0.5px',
        textTransform: 'uppercase',
      }}>
        {title}
      </div>
      {children}
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div style={{
      height: 280,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: 'var(--text-muted)',
    }}>
      {message}
    </div>
  )
}

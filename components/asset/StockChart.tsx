'use client'

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { StockPoint } from '@/lib/types'

interface Props {
  data: StockPoint[]
}

export default function StockChart({ data }: Props) {
  const chartData = data
    .filter(point => point.timestamp)
    .map(point => ({
      ...point,
      ts: new Date(point.timestamp).getTime(),
    }))

  if (chartData.length === 0) {
    return (
      <ChartShell title="Stock Price">
        <EmptyState message="No stock data available" />
      </ChartShell>
    )
  }

  const closes = chartData
    .map(point => point.close)
    .filter((value): value is number => value !== null && value !== undefined && isFinite(value))

  if (closes.length === 0) {
    return (
      <ChartShell title="Stock Price">
        <EmptyState message="No stock data available" />
      </ChartShell>
    )
  }

  const minClose = Math.min(...closes)
  const maxClose = Math.max(...closes)
  const pad = (maxClose - minClose) * 0.08
  const domain: [number, number] = [
    Math.floor((minClose - pad) * 100) / 100,
    Math.ceil((maxClose + pad) * 100) / 100,
  ]
  const openRef = findMarketOpen(chartData)

  return (
    <ChartShell title="Stock Price">
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a3448" />

          <XAxis
            dataKey="ts"
            tickFormatter={formatTime}
            tick={{ fontSize: 10, fill: '#6b7a8d' }}
            tickLine={false}
            axisLine={{ stroke: '#2a3448' }}
            type="number"
            scale="time"
            domain={['dataMin', 'dataMax']}
          />

          <YAxis
            domain={domain}
            tickFormatter={value => `$${value.toFixed(0)}`}
            tick={{ fontSize: 10, fill: '#6b7a8d' }}
            tickLine={false}
            axisLine={false}
          />

          {openRef != null && (
            <ReferenceLine
              x={openRef}
              stroke="#ef4444"
              strokeWidth={1.5}
              label={{ value: 'Market Open', fill: '#ef4444', fontSize: 9, position: 'insideTopRight' }}
            />
          )}

          <Line
            type="monotone"
            dataKey="close"
            stroke="#3b82f6"
            strokeWidth={2}
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
            formatter={value => {
              const numericValue = typeof value === 'number' ? value : null
              return [numericValue == null ? '—' : `$${numericValue.toFixed(2)}`, 'Stock Close']
            }}
            labelFormatter={value => formatTooltipTime(Number(value))}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

function findMarketOpen(data: Array<{ ts: number }>) {
  for (const point of data) {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).formatToParts(new Date(point.ts))
    const hour = Number(parts.find(part => part.type === 'hour')?.value ?? '0')
    const minute = Number(parts.find(part => part.type === 'minute')?.value ?? '0')
    if (hour === 9 && minute === 30) return point.ts
  }
  return data.length > 0 ? data[0].ts : null
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

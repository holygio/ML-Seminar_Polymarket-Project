'use client'

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { SentimentPoint } from '@/lib/types'

interface Props {
  data: SentimentPoint[]
}

export default function TrueSentimentChart({ data }: Props) {
  const chartData = data
    .filter(point => point.timestamp)
    .map(point => ({
      ...point,
      ts: new Date(point.timestamp).getTime(),
    }))
    .filter(point => point.true_sentiment != null)

  if (chartData.length === 0) {
    return (
      <ChartShell>
        <EmptyState message="No true sentiment data available" />
      </ChartShell>
    )
  }

  return (
    <ChartShell>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a3448" vertical={false} />

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
            tick={{ fontSize: 10, fill: '#6b7a8d' }}
            tickFormatter={value => value.toFixed(3)}
            tickLine={false}
            axisLine={false}
          />

          <ReferenceLine y={0} stroke="#6b7a8d" strokeWidth={1} />

          <Bar dataKey="true_sentiment" radius={[2, 2, 0, 0]} isAnimationActive={false}>
            {chartData.map((point, index) => (
              <Cell
                key={point.ts ?? index}
                fill={(point.true_sentiment ?? 0) >= 0 ? '#10b981' : '#ef4444'}
              />
            ))}
          </Bar>

          <Tooltip
            contentStyle={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              fontSize: '12px',
            }}
            formatter={value => {
              const numericValue = typeof value === 'number' ? value : null
              return [numericValue == null ? '—' : numericValue.toFixed(4), 'True Sentiment']
            }}
            labelFormatter={value => formatTooltipTime(Number(value))}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

function ChartShell({ children }: { children: React.ReactNode }) {
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
        marginBottom: '4px',
        fontWeight: 600,
        letterSpacing: '0.5px',
        textTransform: 'uppercase',
      }}>
        True Sentiment
      </div>
      <div style={{
        fontSize: '12px',
        color: 'var(--text-muted)',
        marginBottom: '12px',
      }}>
        PM price minus Black-Scholes fair value - positive means PM more bullish than model
      </div>
      {children}
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div style={{
      height: 220,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: 'var(--text-muted)',
    }}>
      {message}
    </div>
  )
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

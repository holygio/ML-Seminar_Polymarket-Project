'use client'

import Link from 'next/link'
import AssetDaySelector from '@/components/asset/AssetDaySelector'
import type { Ticker } from '@/lib'

const ASSET_META: Record<Ticker, { label: string; category: string }> = {
  AAPL: { label: 'Apple', category: 'US Equities' },
  AMZN: { label: 'Amazon', category: 'US Equities' },
  COIN: { label: 'Coinbase', category: 'US Equities' },
  GOOGL: { label: 'Alphabet', category: 'US Equities' },
  META: { label: 'Meta', category: 'US Equities' },
  MSFT: { label: 'Microsoft', category: 'US Equities' },
  NFLX: { label: 'Netflix', category: 'US Equities' },
  NVDA: { label: 'Nvidia', category: 'US Equities' },
  PLTR: { label: 'Palantir', category: 'US Equities' },
  TSLA: { label: 'Tesla', category: 'US Equities' },
}

interface Props {
  ticker: Ticker
  days: number
  availableTickers: Ticker[]
  lastClose: number | null
  return1D: string | null
  polyProb: number | null
  latestDate: string | null
}

function fmtPrice(value: number | null) {
  if (value === null) return '—'
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtDateLabel(value: string | null) {
  if (!value) return '—'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value.slice(0, 10)
  return dt.toLocaleDateString('en-US', { month: 'short', day: '2-digit' })
}

export default function AssetPageHeader({
  ticker,
  days,
  availableTickers,
  lastClose,
  return1D,
  polyProb,
  latestDate,
}: Props) {
  const meta = ASSET_META[ticker]
  const isPos = !!return1D && return1D.startsWith('+')
  const probColor = polyProb === null ? '#64748b' : polyProb >= 0.5 ? '#60a5fa' : '#f87171'

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: '24px',
        marginBottom: '32px',
        borderBottom: '1px solid #243550',
        paddingBottom: '24px',
        flexWrap: 'wrap',
      }}
    >
      <div style={{ minWidth: '320px', flex: '1 1 420px' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'baseline', flexWrap: 'wrap' }}>
          <h1
            style={{
              fontSize: '36px',
              color: '#f8fafc',
              fontWeight: 400,
              margin: 0,
              fontFamily: '"Courier New", monospace',
              letterSpacing: '2px',
            }}
          >
            {ticker}
          </h1>
          <div
            style={{
              fontSize: '15px',
              color: '#64748b',
              fontFamily: '"Courier New", monospace',
              letterSpacing: '1px',
            }}
          >
            {meta.label} · {meta.category}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '24px', marginTop: '12px', flexWrap: 'wrap' }}>
          <div style={{ fontSize: '24px', color: '#f8fafc', fontFamily: '"Courier New", monospace' }}>
            ${fmtPrice(lastClose)}
          </div>
          <div
            style={{
              fontSize: '13px',
              background: isPos ? '#1a6b3a' : '#2a1010',
              color: isPos ? '#4ade80' : '#f87171',
              padding: '4px 8px',
              borderRadius: '2px',
              fontFamily: '"Courier New", monospace',
            }}
          >
            {return1D ?? 'N/A'}
          </div>
          <div style={{ width: '1px', height: '24px', background: '#243550' }} />
          <div style={{ fontSize: '12px', color: '#64748b', fontFamily: '"Courier New", monospace', lineHeight: 1.2 }}>
            Poly Up
            <br />
            probability
          </div>
          <div style={{ fontSize: '20px', color: probColor, fontFamily: '"Courier New", monospace' }}>
            {polyProb === null ? '—' : `${Math.round(polyProb * 100)}%`}
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', fontFamily: '"Courier New", monospace', lineHeight: 1.2 }}>
            latest
            <br />
            {fmtDateLabel(latestDate)}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', alignItems: 'flex-end', flex: '1 1 420px' }}>
        <AssetDaySelector initialDays={days} />
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {availableTickers.map(assetTicker => {
            const active = assetTicker === ticker
            return (
              <Link
                key={assetTicker}
                href={`/asset/${assetTicker}?days=${days}`}
                style={{
                  padding: '6px 12px',
                  fontSize: '11px',
                  borderRadius: '2px',
                  fontFamily: '"Courier New", monospace',
                  background: active ? '#1a365d' : 'transparent',
                  color: active ? '#60a5fa' : '#475569',
                  border: active ? '1px solid #2563eb' : '1px solid #1e293b',
                  textDecoration: 'none',
                  letterSpacing: '0.8px',
                }}
              >
                {assetTicker}
              </Link>
            )
          })}
        </div>
      </div>
    </div>
  )
}

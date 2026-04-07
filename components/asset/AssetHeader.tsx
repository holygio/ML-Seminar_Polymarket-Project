import { Suspense } from 'react'
import AssetDaySelector from '@/components/asset/AssetDaySelector'

interface Props {
  ticker: string
  overnightChange: number | null
  signalDirection: 'UP' | 'DOWN' | null
  impliedProb: number | null
  days: number
}

export default function AssetHeader({ ticker, overnightChange, signalDirection, impliedProb, days }: Props) {
  const changeColor = overnightChange == null
    ? 'var(--text-muted)'
    : overnightChange > 0 ? 'var(--green)' : 'var(--red)'

  const changeStr = overnightChange == null
    ? '—'
    : `${overnightChange > 0 ? '+' : ''}${(overnightChange * 100).toFixed(1)}%`

  const probStr = impliedProb == null
    ? '—'
    : `${(impliedProb * 100).toFixed(1)}%`

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: '8px',
      padding: '20px 24px',
      display: 'flex',
      alignItems: 'center',
      gap: '32px',
      flexWrap: 'wrap',
    }}>
      <div>
        <div style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-1px' }}>{ticker}</div>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
          Up/Down prediction market
        </div>
      </div>
      <div>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>OVERNIGHT CHANGE</div>
        <div style={{ fontSize: '26px', fontWeight: 700, color: changeColor, fontFamily: 'var(--mono)' }}>
          {changeStr}
        </div>
      </div>
      <div>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>PRE-OPEN PROB</div>
        <div style={{ fontSize: '22px', fontWeight: 600, fontFamily: 'var(--mono)' }}>{probStr}</div>
      </div>
      <div style={{ marginLeft: 'auto' }}>
        <Suspense fallback={null}>
          <AssetDaySelector initialDays={days} />
        </Suspense>
      </div>
      {signalDirection && (
        <div style={{
          background: signalDirection === 'UP' ? 'var(--green-dim)' : 'var(--red-dim)',
          border: `1px solid ${signalDirection === 'UP' ? 'var(--green)' : 'var(--red)'}`,
          color: signalDirection === 'UP' ? 'var(--green)' : 'var(--red)',
          borderRadius: '6px',
          padding: '8px 20px',
          fontSize: '16px',
          fontWeight: 700,
          letterSpacing: '1px',
        }}>
          {signalDirection === 'UP' ? '▲ BUY' : '▼ SELL'}
        </div>
      )}
    </div>
  )
}

'use client'

import type { SignalToday } from '@/lib'

export default function ModelSnapshot({
  signal,
  ticker,
  days = 30,
}: {
  signal: SignalToday | null
  ticker: string
  days?: number
}) {
  const ts = signal?.true_sentiment !== null && signal?.true_sentiment !== undefined ? signal.true_sentiment : 0
  const bs = signal?.bs_neutral_prob !== null && signal?.bs_neutral_prob !== undefined ? signal.bs_neutral_prob : 0.5
  const avgUp = signal?.pre_open_implied_prob !== null && signal?.pre_open_implied_prob !== undefined ? signal.pre_open_implied_prob : 0.5
  const volAnn = signal?.stock_vol_ann !== null && signal?.stock_vol_ann !== undefined ? signal.stock_vol_ann : 0.412
  const excess = (avgUp - bs) * 100

  return (
    <div style={{ marginBottom: '32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '24px' }}>
        <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#a855f7' }} />
        <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '2px', fontFamily: '"Courier New", monospace' }}>
          MODEL SNAPSHOT
        </div>
      </div>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px', marginBottom: '24px' }}>
        <div style={{ padding: '12px', border: '1px solid #1e293b', borderRadius: '2px' }}>
          <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px', fontFamily: '"Courier New", monospace', marginBottom: '8px' }}>
            TRUE SENTIMENT
          </div>
          <div style={{ fontSize: '18px', color: ts > 0 ? '#22c55e' : '#ef4444', fontFamily: '"Courier New", monospace' }}>
            {ts > 0 ? '+' : ''}{ts.toFixed(3)}
          </div>
        </div>
        
        <div style={{ padding: '12px', border: '1px solid #1e293b', borderRadius: '2px' }}>
          <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px', fontFamily: '"Courier New", monospace', marginBottom: '8px' }}>
            BLACK-SCHOLES NEUTRAL
          </div>
          <div style={{ fontSize: '18px', color: '#f8fafc', fontFamily: '"Courier New", monospace' }}>
            {bs.toFixed(3)}
          </div>
        </div>
        
        <div style={{ padding: '12px', border: '1px solid #1e293b', borderRadius: '2px' }}>
          <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px', fontFamily: '"Courier New", monospace', marginBottom: '8px' }}>
            AVG PRICE UP
          </div>
          <div style={{ fontSize: '18px', color: '#38bdf8', fontFamily: '"Courier New", monospace' }}>
            {avgUp.toFixed(3)}
          </div>
        </div>
        
        <div style={{ padding: '12px', border: '1px solid #1e293b', borderRadius: '2px' }}>
          <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px', fontFamily: '"Courier New", monospace', marginBottom: '8px' }}>
            STOCK VOL (ANN)
          </div>
          <div style={{ fontSize: '18px', color: '#f8fafc', fontFamily: '"Courier New", monospace' }}>
            {volAnn.toFixed(3)}
          </div>
        </div>
      </div>
      
      <div style={{ background: 'transparent', borderLeft: '2px solid #1e3a8a', paddingLeft: '16px' }}>
        <div style={{ fontSize: '10px', color: '#475569', textTransform: 'uppercase', letterSpacing: '2px', fontFamily: '"Courier New", monospace', marginBottom: '12px' }}>
          SIGNAL INTERPRETATION
        </div>
        <div style={{ fontSize: '12px', color: '#64748b', lineHeight: 1.6, fontFamily: '"Courier New", monospace' }}>
          Crowd assigns {(avgUp * 100).toFixed(1)}% up-probability. BS fair value at current vol ({(volAnn * 100).toFixed(1)}% ann) and time to close puts neutral at {(bs * 100).toFixed(1)}%. The {excess.toFixed(1)}pp excess is dynamically captured for {ticker} over the last {days} days.
        </div>
      </div>
    </div>
  )
}

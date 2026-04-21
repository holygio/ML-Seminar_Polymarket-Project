'use client'

import type { SignalToday } from '@/lib'

export default function SignalQualityPanel({ signal }: { signal: SignalToday | null }) {
  const score = signal?.signal_quality_score ?? 10
  const color = score > 7 ? '#22c55e' : score > 4 ? '#fbbf24' : '#ef4444'
  const hasSignal = signal !== null

  return (
    <div style={{ marginBottom: '40px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '24px' }}>
        <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#22c55e' }} />
        <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '2px', fontFamily: '"Courier New", monospace' }}>
          SIGNAL QUALITY
        </div>
      </div>
      
      <div style={{ display: 'flex', gap: '24px', alignItems: 'center', marginBottom: '24px' }}>
        <div style={{ position: 'relative', width: '70px', height: '70px' }}>
          <svg viewBox="0 0 100 100" style={{ width: '100%', height: '100%', transform: 'rotate(-90deg)' }}>
            <circle cx="50" cy="50" r="45" fill="none" stroke="#1e293b" strokeWidth="6" />
            <circle cx="50" cy="50" r="45" fill="none" stroke={color} strokeWidth="6" strokeDasharray="282" strokeDashoffset={282 - (282 * (score / 10))} strokeLinecap="round" />
          </svg>
          <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', fontFamily: '"Courier New", monospace' }}>
            <div style={{ fontSize: '24px', color, lineHeight: 1 }}>{Math.round(score)}</div>
            <div style={{ fontSize: '10px', color: '#64748b' }}>/10</div>
          </div>
        </div>
        
        <div>
          <div style={{ display: 'inline-flex', padding: '4px 8px', border: `1px solid ${color}`, borderRadius: '2px', fontSize: '11px', color, fontFamily: '"Courier New", monospace', marginBottom: '8px' }}>
            {signal?.signal_direction === 'up' ? 'UP SIGNAL' : signal?.signal_direction === 'down' ? 'DOWN SIGNAL' : 'NEUTRAL'}
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', fontFamily: '"Courier New", monospace', letterSpacing: '0.5px' }}>
            {hasSignal ? 'Derived from the latest pre-open snapshot' : 'Waiting for a usable pre-open snapshot'}
          </div>
          <div style={{ marginTop: '12px', height: '4px', width: '120px', background: 'linear-gradient(90deg, #1e3a8a, #38bdf8)', borderRadius: '2px' }} />
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', fontFamily: '"Courier New", monospace', fontSize: '13px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ color: '#475569' }}>Pre-open prob</div>
          <div style={{ color: '#38bdf8' }}>{signal?.pre_open_implied_prob !== null && signal?.pre_open_implied_prob !== undefined ? signal.pre_open_implied_prob.toFixed(4) : '—'}</div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ color: '#475569' }}>Overnight &Delta; prob</div>
          <div style={{ color: (signal?.overnight_prob_change ?? 0) >= 0 ? '#22c55e' : '#ef4444' }}>
            {signal?.overnight_prob_change !== null && signal?.overnight_prob_change !== undefined
              ? `${signal.overnight_prob_change > 0 ? '+' : ''}${(signal.overnight_prob_change * 100).toFixed(4)}`
              : '—'}
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ color: '#475569' }}>PM volume</div>
          <div style={{ color: '#f8fafc' }}>
            {signal?.pre_open_pm_volume !== null && signal?.pre_open_pm_volume !== undefined
              ? `${signal.pre_open_pm_volume.toLocaleString()} USDC`
              : '—'}
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ color: '#475569' }}>Buy ratio</div>
          <div style={{ color: '#f8fafc' }}>
            {signal?.pre_open_buy_ratio !== null && signal?.pre_open_buy_ratio !== undefined
              ? signal.pre_open_buy_ratio.toFixed(2)
              : '—'}
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ color: '#475569' }}>High liquidity</div>
          <div style={{ color: signal?.is_high_liquidity !== false ? '#22c55e' : '#ef4444' }}>
            {signal?.is_high_liquidity !== false ? 'Yes' : 'No'}
          </div>
        </div>
      </div>
    </div>
  )
}

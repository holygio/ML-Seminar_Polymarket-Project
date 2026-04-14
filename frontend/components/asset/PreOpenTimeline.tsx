'use client'

import type { ProbabilityPoint } from '@/lib'

export default function PreOpenTimeline({ data }: { data: ProbabilityPoint[] }) {
  const displayData = data.slice(-7).map(d => ({
    time: d.timestamp.includes('T') ? d.timestamp.split('T')[1].substring(0, 5) : d.timestamp,
    prob: d.price_up || 0.5
  }))

  return (
    <div style={{ marginBottom: '40px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '24px' }}>
        <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#38bdf8' }} />
        <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '2px', fontFamily: '"Courier New", monospace' }}>
          PRE-OPEN PROBABILITY TRACK
        </div>
      </div>
      
      {displayData.length === 0 ? (
        <div style={{ fontSize: '12px', color: '#475569', fontFamily: '"Courier New", monospace', fontStyle: 'italic', padding: '12px 0' }}>
          No pre-open orderbook data available.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontFamily: '"Courier New", monospace', fontSize: '11px' }}>
          {displayData.map((d, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ color: '#475569', width: '40px' }}>{d.time}</div>
              <div style={{ flex: 1, height: '6px', background: '#1e293b', borderRadius: '1px' }}>
                <div style={{ height: '100%', width: `${d.prob * 100}%`, background: '#38bdf8', borderRadius: '1px' }} />
              </div>
              <div style={{ color: '#38bdf8', width: '32px', textAlign: 'right' }}>{d.prob.toFixed(2)}</div>
            </div>
          ))}
        </div>
      )}
      
      <div style={{ marginTop: '16px', fontSize: '10px', color: '#475569', fontFamily: '"Courier New", monospace', display: 'flex', gap: '8px' }}>
        <span>&#9650;</span>
        <span>firewall 09:30 &mdash; signal locked</span>
      </div>
    </div>
  )
}

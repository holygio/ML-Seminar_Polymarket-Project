'use client'

import { AreaChart, Area, YAxis, ResponsiveContainer } from 'recharts'
import type { SentimentPoint } from '@/lib'

export default function TrueSentimentPanel({ tsData }: { tsData: SentimentPoint[] | undefined }) {
  const latestTs = tsData && tsData.length > 0 ? tsData[tsData.length - 1].true_sentiment : null
  const isPos = latestTs && latestTs > 0
  const color = isPos ? '#22c55e' : '#ef4444'
  const trackDays = tsData && tsData.length > 1 ? new Set(tsData.map(point => point.timestamp.slice(0, 10))).size : 1

  return (
    <div style={{ marginBottom: '32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '24px' }}>
        <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#a855f7' }} />
        <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '2px', fontFamily: '"Courier New", monospace' }}>
          TRUE SENTIMENT (BS-ADJUSTED SIGNAL)
        </div>
      </div>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <div style={{ fontSize: '10px', color: '#475569', textTransform: 'uppercase', letterSpacing: '1px', fontFamily: '"Courier New", monospace', marginBottom: '8px' }}>
            CURRENT READING
          </div>
          <div style={{ fontSize: '32px', color, fontFamily: '"Courier New", monospace' }}>
            {latestTs !== null ? `${latestTs > 0 ? '+' : ''}${(latestTs).toFixed(3)}` : '—'}
          </div>
          <div style={{ fontSize: '10px', color: '#475569', fontFamily: '"Courier New", monospace', marginTop: '4px' }}>
            crowd more {isPos ? 'bullish' : 'bearish'} than BS fair value
          </div>
        </div>
        
        <div style={{ width: '200px', height: '60px' }}>
          <div style={{ fontSize: '10px', color: '#475569', fontFamily: '"Courier New", monospace', marginBottom: '4px', textAlign: 'center' }}>
            {trackDays}D true sentiment track
          </div>
          <ResponsiveContainer width="100%" height="80%">
            <AreaChart data={tsData || []}>
              <defs>
                <linearGradient id="colorTs" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={color} stopOpacity={0.3}/>
                  <stop offset="95%" stopColor={color} stopOpacity={0}/>
                </linearGradient>
              </defs>
              <YAxis domain={[-1, 1]} hide />
              <Area type="monotone" dataKey="true_sentiment" stroke={color} strokeWidth={1.5} fill="url(#colorTs)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
      
      <div style={{ width: '100%' }}>
        <div style={{ display: 'flex', height: '12px', background: '#0a1628', position: 'relative' }}>
          <div style={{ width: '50%', background: 'linear-gradient(to right, #0a1628, #1a2840)' }} />
          <div style={{ width: '50%', background: 'linear-gradient(to right, #1a2840, #22c55e)' }} />
          <div style={{ position: 'absolute', left: '0', top: 0, bottom: 0, borderLeft: '1px solid #1e293b' }} />
          <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, borderLeft: '1px solid #1e293b' }} />
          <div style={{ position: 'absolute', right: '0', top: 0, bottom: 0, borderRight: '1px solid #1e293b' }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px', fontSize: '9px', color: '#475569', fontFamily: '"Courier New", monospace' }}>
          <div>Bearish crowd</div>
          <div>Neutral</div>
          <div>Bullish crowd</div>
        </div>
      </div>
    </div>
  )
}

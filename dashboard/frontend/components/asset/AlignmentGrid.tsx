'use client'

import type { HeatmapEntry } from '@/lib'

export default function AlignmentGrid({
  data,
  maxDays = 30,
}: {
  data: HeatmapEntry[]
  maxDays?: number
}) {
  const sorted = [...data].sort((a, b) => b.date.localeCompare(a.date)).slice(0, maxDays)

  const totalCells = Math.max(maxDays, sorted.length)
  const cells = Array.from({ length: totalCells }, (_, i) => {
    const entry = sorted[i]
    return entry
      ? { type: 'data' as const, entry }
      : { type: 'empty' as const }
  })

  let aligned = 0, opposed = 0, mixed = 0, lowVol = 0
  sorted.forEach(entry => {
    if (entry.quadrant === 'green') aligned++
    else if (entry.quadrant === 'red') opposed++
    else if (entry.quadrant === 'yellow') mixed++
    else if (entry.quadrant === 'gray') lowVol++
  })

  const totalValid = aligned + opposed
  const hitRate = totalValid > 0 ? (aligned / totalValid) * 100 : 0

  return (
    <div style={{ marginBottom: '32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '24px' }}>
        <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#eab308' }} />
        <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '2px', fontFamily: '"Courier New", monospace' }}>
          HISTORICAL ALIGNMENT &middot; LAST {maxDays} DAYS
        </div>
      </div>
      
      <div style={{ display: 'flex', gap: '24px', alignItems: 'flex-start' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(10, 1fr)', gap: '2px', flex: 1 }}>
          {cells.map((cell, i) => {
            if (cell.type === 'empty') {
              return (
                <div
                  key={`empty-${i}`}
                  style={{
                    aspectRatio: '1',
                    background: '#0f172a',
                    border: '1px solid #0f172a',
                    opacity: 0.35
                  }}
                />
              )
            }

            const { entry } = cell
            let bg = '#475569'
            if (entry.quadrant === 'green') bg = '#22c55e'
            else if (entry.quadrant === 'red') bg = '#dc2626'
            else if (entry.quadrant === 'yellow') bg = '#b45309'
            
            return (
              <div 
                key={entry.date || i} 
                title={`${entry.date} | PM: ${entry.prob_change?.toFixed(2)}% | Price: ${entry.price_move?.toFixed(2)}%`}
                style={{
                  aspectRatio: '1',
                  background: bg,
                  border: '1px solid #0f172a',
                  cursor: 'help'
                }} 
              />
            )
          })}
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '120px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px', color: '#64748b', fontFamily: '"Courier New", monospace' }}>
            <div style={{ width: '10px', height: '10px', background: '#22c55e' }} /> Aligned {aligned}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px', color: '#64748b', fontFamily: '"Courier New", monospace' }}>
            <div style={{ width: '10px', height: '10px', background: '#dc2626' }} /> Opposed {opposed}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px', color: '#64748b', fontFamily: '"Courier New", monospace' }}>
            <div style={{ width: '10px', height: '10px', background: '#b45309' }} /> Mixed {mixed}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px', color: '#64748b', fontFamily: '"Courier New", monospace' }}>
            <div style={{ width: '10px', height: '10px', background: '#475569' }} /> Low vol {lowVol}
          </div>
          
          <div style={{ marginTop: '4px', paddingTop: '8px', borderTop: '1px solid #1e293b', fontSize: '11px', color: '#22c55e', fontFamily: '"Courier New", monospace', fontWeight: 600 }}>
            {hitRate.toFixed(1)}% hit
          </div>
        </div>
      </div>
    </div>
  )
}

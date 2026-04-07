'use client'

import { useEffect, useState } from 'react'
import { fetchHeatmap } from '@/lib/api'
import type { HeatmapEntry } from '@/lib/types'
import AlignmentGrid from '@/components/heatmap/AlignmentGrid'
import AlignmentSummaryStats from '@/components/heatmap/AlignmentSummaryStats'
import QuadrantLegend from '@/components/heatmap/QuadrantLegend'
import TimeFilterBar from '@/components/heatmap/TimeFilterBar'

export default function HeatmapPage() {
  const [days, setDays] = useState(30)
  const [data, setData] = useState<HeatmapEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchHeatmap(days)
      .then(res => setData(res.data))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [days])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: '16px',
        flexWrap: 'wrap',
      }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '4px' }}>
            Signal Alignment Heatmap
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Did Polymarket probability direction match stock price direction?
          </p>
        </div>
        <TimeFilterBar selected={days} onChange={setDays} />
      </div>

      <QuadrantLegend />

      {loading && (
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          height: '320px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-muted)',
          fontSize: '13px',
        }}>
          Loading heatmap...
        </div>
      )}

      {error && (
        <div style={{
          background: 'var(--red-dim)',
          border: '1px solid var(--red)',
          borderRadius: '6px',
          padding: '12px 16px',
          color: 'var(--red)',
          fontSize: '13px',
        }}>
          {error}
        </div>
      )}

      {!loading && !error && (
        <>
          <AlignmentGrid data={data} />
          <AlignmentSummaryStats data={data} />
        </>
      )}
    </div>
  )
}

import type { HeatmapEntry } from '@/lib/types'

interface Props {
  data: HeatmapEntry[]
}

export default function AlignmentSummaryStats({ data }: Props) {
  if (data.length === 0) return null

  const alignedQuadrants = new Set(['green', 'red'])
  const nonGray = data.filter(item => item.quadrant !== 'gray')
  const aligned = nonGray.filter(item => alignedQuadrants.has(item.quadrant))
  const highLiquidity = data.filter(item => item.volume >= 500)
  const highLiquidityDirectional = highLiquidity.filter(item => item.quadrant !== 'gray')
  const highLiquidityAligned = highLiquidityDirectional.filter(item => alignedQuadrants.has(item.quadrant))

  const overallRate = nonGray.length > 0 ? aligned.length / nonGray.length : 0
  const highLiquidityRate = highLiquidityDirectional.length > 0
    ? highLiquidityAligned.length / highLiquidityDirectional.length
    : 0

  const grouped = groupByTicker(nonGray)
  let bestTicker = '—'
  let bestRate = 0
  let worstTicker = '—'
  let worstRate = 0
  let first = true

  for (const [ticker, entries] of Object.entries(grouped)) {
    if (entries.length === 0) continue
    const rate = entries.filter(item => alignedQuadrants.has(item.quadrant)).length / entries.length
    if (first || rate > bestRate) {
      bestTicker = ticker
      bestRate = rate
    }
    if (first || rate < worstRate) {
      worstTicker = ticker
      worstRate = rate
    }
    first = false
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
      <StatCard
        label="Overall Alignment"
        value={`${Math.round(overallRate * 100)}%`}
        sub={`${aligned.length} of ${nonGray.length} directional signals`}
      />
      <StatCard
        label="High-Liq Alignment"
        value={`${Math.round(highLiquidityRate * 100)}%`}
        sub={`volume > $500 only (${highLiquidityDirectional.length} obs)`}
        highlight
      />
      <StatCard
        label="Best Asset"
        value={bestTicker}
        sub={`${Math.round(bestRate * 100)}% alignment rate`}
        valueColor="var(--green)"
      />
      <StatCard
        label="Worst Asset"
        value={worstTicker}
        sub={`${Math.round(worstRate * 100)}% alignment rate`}
        valueColor="var(--red)"
      />
    </div>
  )
}

function StatCard({
  label,
  value,
  sub,
  highlight = false,
  valueColor,
}: {
  label: string
  value: string
  sub: string
  highlight?: boolean
  valueColor?: string
}) {
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: `1px solid ${highlight ? 'var(--accent)' : 'var(--border)'}`,
      borderRadius: '8px',
      padding: '16px',
    }}>
      <div style={{
        fontSize: '11px',
        color: 'var(--text-muted)',
        fontWeight: 600,
        textTransform: 'uppercase',
      }}>
        {label}
      </div>
      <div style={{
        fontSize: '24px',
        fontWeight: 800,
        fontFamily: 'var(--mono)',
        color: valueColor ?? 'var(--text)',
      }}>
        {value}
      </div>
      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
        {sub}
      </div>
    </div>
  )
}

function groupByTicker(data: HeatmapEntry[]) {
  return data.reduce<Record<string, HeatmapEntry[]>>((acc, item) => {
    if (!acc[item.ticker]) acc[item.ticker] = []
    acc[item.ticker].push(item)
    return acc
  }, {})
}

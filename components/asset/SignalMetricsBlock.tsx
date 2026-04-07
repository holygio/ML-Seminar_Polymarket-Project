import type { SignalToday } from '@/lib/types'

interface Props {
  signal: SignalToday | null
}

export default function SignalMetricsBlock({ signal }: Props) {
  if (!signal) return null

  const absSentiment = signal.true_sentiment == null ? null : Math.abs(signal.true_sentiment)
  const score = signal.signal_quality_score ?? 0
  const scoreColor = score >= 7 ? 'var(--green)' : score >= 4 ? 'var(--yellow)' : 'var(--red)'

  const conviction = absSentiment == null
    ? '—'
    : absSentiment >= 0.05 ? 'HIGH'
    : absSentiment >= 0.02 ? 'MEDIUM'
    : 'LOW'

  const convictionColor = conviction === 'HIGH'
    ? 'var(--green)'
    : conviction === 'MEDIUM'
      ? 'var(--yellow)'
      : conviction === 'LOW'
        ? 'var(--text-muted)'
        : 'var(--text-muted)'

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '20px',
      }}>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '16px' }}>
          PRE-OPEN POLYMARKET METRICS
        </div>

        <MetricRow
          label="Implied Probability"
          value={signal.pre_open_implied_prob != null ? `${(signal.pre_open_implied_prob * 100).toFixed(1)}%` : '—'}
        />
        <MetricRow
          label="Overnight Change"
          value={signal.overnight_prob_change != null
            ? `${signal.overnight_prob_change > 0 ? '+' : ''}${(signal.overnight_prob_change * 100).toFixed(2)}%`
            : '—'}
          color={signal.overnight_prob_change == null
            ? undefined
            : signal.overnight_prob_change > 0 ? 'var(--green)' : 'var(--red)'}
        />
        <MetricRow
          label="Pre-Open Volume"
          value={`$${Math.round(signal.pre_open_pm_volume).toLocaleString()}`}
          badge={signal.is_high_liquidity
            ? { label: 'HIGH LIQ', color: 'var(--green)' }
            : { label: 'LOW LIQ', color: 'var(--red)' }}
        />
        <MetricRow
          label="True Sentiment"
          value={signal.true_sentiment == null ? '—' : signal.true_sentiment.toFixed(4)}
          color={signal.true_sentiment == null
            ? 'var(--text-muted)'
            : signal.true_sentiment >= 0 ? 'var(--green)' : 'var(--red)'}
        />
        <MetricRow
          label="Conviction"
          value={conviction}
          color={convictionColor}
        />
      </div>

      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        padding: '20px',
      }}>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '16px' }}>
          SIGNAL QUALITY SCORE
        </div>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px', marginBottom: '20px' }}>
          <span style={{ fontSize: '48px', fontWeight: 800, color: scoreColor, fontFamily: 'var(--mono)' }}>
            {score.toFixed(1)}
          </span>
          <span style={{ fontSize: '20px', color: 'var(--text-muted)' }}>/10</span>
        </div>

        <div style={{ marginBottom: '16px' }}>
          <div style={{ background: 'var(--border)', borderRadius: '4px', height: '6px', width: '100%' }}>
            <div style={{
              background: scoreColor,
              borderRadius: '4px',
              height: '6px',
              width: `${Math.max(0, Math.min(score, 10)) * 10}%`,
              transition: 'width 0.4s ease',
            }} />
          </div>
        </div>

        <ScoreRow label="Volume" pass={signal.pre_open_pm_volume >= 500} />
        <ScoreRow label="Liquidity" pass={signal.is_high_liquidity} />
        <ScoreRow label="Conviction" pass={absSentiment != null && absSentiment >= 0.02} />
        <ScoreRow label="Data exists" pass />
      </div>
    </div>
  )
}

function MetricRow({
  label,
  value,
  color,
  badge,
}: {
  label: string
  value: string
  color?: string
  badge?: { label: string; color: string }
}) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '8px 0',
      borderBottom: '1px solid var(--border)',
    }}>
      <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {badge && (
          <span style={{
            fontSize: '10px',
            padding: '2px 6px',
            borderRadius: '3px',
            background: `${badge.color}22`,
            color: badge.color,
            fontWeight: 600,
          }}>
            {badge.label}
          </span>
        )}
        <span style={{ fontSize: '14px', fontWeight: 600, color: color ?? 'var(--text)', fontFamily: 'var(--mono)' }}>
          {value}
        </span>
      </div>
    </div>
  )
}

function ScoreRow({ label, pass }: { label: string; pass: boolean }) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      padding: '5px 0',
      fontSize: '13px',
    }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ color: pass ? 'var(--green)' : 'var(--red)' }}>
        {pass ? '✓' : '✗'}
      </span>
    </div>
  )
}

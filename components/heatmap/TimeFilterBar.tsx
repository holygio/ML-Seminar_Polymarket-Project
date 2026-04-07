interface Props {
  selected: number
  onChange: (days: number) => void
}

const OPTIONS = [
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
  { label: '60D', days: 60 },
]

export default function TimeFilterBar({ selected, onChange }: Props) {
  return (
    <div style={{ display: 'flex', gap: '4px' }}>
      {OPTIONS.map(opt => (
        <button
          key={opt.days}
          onClick={() => onChange(opt.days)}
          style={{
            padding: '6px 14px',
            borderRadius: '5px',
            border: '1px solid var(--border)',
            background: selected === opt.days ? 'var(--accent)' : 'var(--bg-card)',
            color: selected === opt.days ? 'white' : 'var(--text-muted)',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

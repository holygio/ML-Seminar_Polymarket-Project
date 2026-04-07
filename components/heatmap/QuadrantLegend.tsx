const QUADRANTS = [
  { color: '#10b981', label: 'Aligned Bullish', desc: 'Prob ↑ & Price ↑' },
  { color: '#ef4444', label: 'Aligned Bearish', desc: 'Prob ↓ & Price ↓' },
  { color: '#f59e0b', label: 'Divergent', desc: 'Prob and price disagree' },
  { color: '#374151', label: 'No Signal', desc: 'Low volume or small move' },
]

export default function QuadrantLegend() {
  return (
    <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
      {QUADRANTS.map(item => (
        <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '12px',
            height: '12px',
            borderRadius: '2px',
            background: item.color,
          }} />
          <div>
            <span style={{ fontSize: '12px', fontWeight: 600 }}>{item.label}</span>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '6px' }}>
              {item.desc}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

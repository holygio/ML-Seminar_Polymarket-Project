'use client'

import { usePathname, useRouter, useSearchParams } from 'next/navigation'

const OPTIONS = [
  { label: '1D', days: 1 },
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
]

export default function AssetDaySelector({ initialDays = 1 }: { initialDays?: number }) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const current = parseInt(searchParams.get('days') ?? String(initialDays), 10)

  return (
    <div style={{ display: 'flex', gap: '4px' }}>
      {OPTIONS.map(opt => (
        <button
          key={opt.days}
          onClick={() => router.push(`${pathname}?days=${opt.days}`)}
          style={{
            padding: '4px 10px',
            borderRadius: '4px',
            border: '1px solid var(--border)',
            background: current === opt.days ? 'var(--accent)' : 'var(--bg)',
            color: current === opt.days ? 'white' : 'var(--text-muted)',
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

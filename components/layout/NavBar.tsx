'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { ALL_TICKERS, type Ticker } from '@/lib/types'

export default function NavBar() {
  const pathname = usePathname()
  const router = useRouter()

  const currentTicker = pathname.startsWith('/asset/')
    ? (pathname.split('/')[2]?.toUpperCase() as Ticker | undefined) ?? ''
    : ''

  return (
    <nav style={{
      background: 'var(--bg-card)',
      borderBottom: '1px solid var(--border)',
      padding: '0 24px',
      height: '52px',
      display: 'flex',
      alignItems: 'center',
      gap: '24px',
    }}>
      <span style={{ fontWeight: 700, fontSize: '15px', color: 'var(--accent)' }}>
        PM Signals
      </span>
      <select
        value={currentTicker}
        onChange={e => router.push(`/asset/${e.target.value}`)}
        style={{
          background: 'var(--bg)',
          color: 'var(--text)',
          border: '1px solid var(--border)',
          padding: '4px 8px',
          borderRadius: '4px',
          fontSize: '13px',
          cursor: 'pointer',
        }}
      >
        <option value="" disabled>Select asset</option>
        {ALL_TICKERS.map(t => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>
      <Link href="/heatmap" style={{
        color: pathname === '/heatmap' ? 'var(--accent)' : 'var(--text-muted)',
        fontSize: '13px',
        textDecoration: 'none',
      }}>
        Heatmap
      </Link>
    </nav>
  )
}

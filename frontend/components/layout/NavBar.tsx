'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

export default function NavBar() {
  const pathname = usePathname()

  return (
    <nav style={{
      background: '#040914',
      borderBottom: '1px solid #1a2840',
      padding: '0 24px',
      height: '60px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      fontFamily: '"Courier New", monospace'
    }}>
      <div style={{ color: '#475569', fontSize: '14px', letterSpacing: '4px' }}>
        POLYMARKET SIGNAL
      </div>

      <div style={{ display: 'flex', gap: '32px' }}>
        <Link href="/live" style={{
          color: pathname === '/live' ? '#60a5fa' : '#64748b',
          fontSize: '12px',
          textDecoration: 'none',
          letterSpacing: '2px',
          paddingBottom: '20px',
          borderBottom: pathname === '/live' ? '2px solid #60a5fa' : '2px solid transparent',
          transform: 'translateY(11px)'
        }}>
          MARKETS
        </Link>
        <Link href="/geopolitical" style={{
          color: pathname === '/geopolitical' ? '#60a5fa' : '#64748b',
          fontSize: '12px',
          textDecoration: 'none',
          letterSpacing: '2px',
          paddingBottom: '20px',
          borderBottom: pathname === '/geopolitical' ? '2px solid #60a5fa' : '2px solid transparent',
          transform: 'translateY(11px)'
        }}>
          GEOPOLITICAL
        </Link>
        <Link href="/asset/NVDA" style={{
          color: pathname.startsWith('/asset') ? '#60a5fa' : '#64748b',
          fontSize: '12px',
          textDecoration: 'none',
          letterSpacing: '2px',
          paddingBottom: '20px',
          borderBottom: pathname.startsWith('/asset') ? '2px solid #60a5fa' : '2px solid transparent',
          transform: 'translateY(11px)'
        }}>
          ASSET
        </Link>
      </div>

      <div style={{ color: '#475569', fontSize: '12px', letterSpacing: '2px' }}>
        market intelligence
      </div>
    </nav>
  )
}

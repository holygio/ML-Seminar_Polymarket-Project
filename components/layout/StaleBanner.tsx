'use client'

import { useEffect, useState } from 'react'
import { fetchHealth } from '@/lib/api'

export default function StaleBanner() {
  const [stale, setStale] = useState(false)
  const [hoursAgo, setHoursAgo] = useState<number | null>(null)

  useEffect(() => {
    const check = () => {
      fetchHealth()
        .then(h => {
          setStale(h.status === 'stale' || h.status === 'no_data')
          setHoursAgo(h.hours_ago)
        })
        .catch(() => setStale(true))
    }
    check()
    const interval = setInterval(check, 60_000)
    return () => clearInterval(interval)
  }, [])

  if (!stale) return null

  return (
    <div style={{
      background: 'var(--yellow)',
      color: '#000',
      padding: '6px 24px',
      fontSize: '12px',
      fontWeight: 600,
      textAlign: 'center',
    }}>
      {`Data is ${hoursAgo ? `${Math.round(hoursAgo)}h` : ''} old - pipeline may not have run today`}
    </div>
  )
}

'use client'

import { useEffect, useState } from 'react'
import { fetchHealth } from '@/lib'

export default function StaleBanner() {
  const [stale, setStale] = useState(false)
  const [hoursAgo, setHoursAgo] = useState<number | null>(null)
  const [runDate, setRunDate] = useState<string | null>(null)

  useEffect(() => {
    const check = () => {
      fetchHealth()
        .then(h => {
          setStale(h.status === 'stale' || h.status === 'no_data')
          setHoursAgo(h.hours_ago)
          setRunDate(h.date)
        })
        .catch(() => setStale(true))
    }
    check()
    const interval = setInterval(check, 60_000)
    return () => clearInterval(interval)
  }, [])

  if (!stale) return null

  const daysAgo = hoursAgo !== null ? Math.max(0, Math.floor(hoursAgo / 24)) : null
  const freshness = runDate
    ? `Data from ${runDate}${daysAgo !== null ? `, ${daysAgo} day${daysAgo === 1 ? '' : 's'} old` : ''}`
    : 'Data freshness unknown'

  return (
    <div style={{
      background: '#2a1010',
      color: '#fecaca',
      padding: '6px 24px',
      fontSize: '12px',
      fontWeight: 600,
      textAlign: 'center',
      borderBottom: '1px solid #3b1a1a',
    }}>
      {`${freshness} - pipeline may not have completed a recent run`}
    </div>
  )
}

import type { Metadata } from 'next'
import './globals.css'
import NavBar from '@/components/layout/NavBar'
import StaleBanner from '@/components/layout/StaleBanner'

export const metadata: Metadata = {
  title: 'Polymarket Signal Dashboard',
  description: 'Prediction market signals for traditional assets',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <StaleBanner />
        <NavBar />
        <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px' }}>
          {children}
        </main>
      </body>
    </html>
  )
}

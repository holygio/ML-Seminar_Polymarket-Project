'use client'

import { useEffect, useState } from 'react'
import { Treemap, ResponsiveContainer } from 'recharts'
import {
  diagColors,
  fetchLive,
  fmtPrice,
  fmtProb,
  fmtRet,
  fmtSentiment,
  polyColor,
  retColor,
  sentimentColor,
  type LiveRecord,
} from '@/lib'


// ─── Banner ──────────────────────────────────────────
function getSparkline(ret: number | null) {
  if (ret === null) return <svg width="80" height="18" />
  const c = retColor(ret)
  const isUp = ret >= 0
  let y = isUp ? 16 : 2
  const step = isUp ? -1.5 : 1.5
  const seed = Math.abs(ret * 100)
  
  const pts = []
  for (let i = 0; i < 9; i++) {
    const x = i * 10
    const noise = Math.sin(seed + i * 3.14) * 3
    pts.push(`${x},${Math.max(2, Math.min(16, y + noise))}`)
    y += step
  }
  return (
    <svg width="80" height="18" style={{ display: 'block' }}>
      <polyline points={pts.join(' ')} fill="none" stroke={c} strokeWidth="1.2" strokeLinejoin="round" />
    </svg>
  )
}

function Banner({ records }: { records: LiveRecord[] }) {
  const equities = records.filter(r => r.category === 'US Equities')
  if (equities.length === 0) return null

  const duped = [...equities, ...equities]
  const duration = equities.length * 3

  return (
    <div style={{
      width: '100%',
      height: '52px',
      background: '#0a1422',
      borderBottom: '1px solid #1e3348',
      overflow: 'hidden',
      display: 'flex',
      alignItems: 'center',
    }}>
      <style>{`
        @keyframes scrollBanner {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
      <div style={{
        display: 'flex',
        animation: `scrollBanner ${duration}s linear infinite`,
        width: 'max-content',
      }}>
        {duped.map((rec, i) => (
          <div key={i} style={{
            minWidth: '140px',
            borderRight: '1px solid #182840',
            padding: '4px 16px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '11px', letterSpacing: '2px', color: '#94a3b8' }}>
                {rec.ticker}
              </span>
              <span style={{ fontSize: '11px', color: retColor(rec.ret_pct) }}>
                {fmtRet(rec.ret_pct)}
              </span>
            </div>
            <div style={{ padding: '2px 0' }}>
              {getSparkline(rec.ret_pct)}
            </div>
            {rec.true_sentiment !== null && (
              <div style={{
                fontSize: '9px',
                color: sentimentColor(rec.true_sentiment),
                fontFamily: "'Courier New', monospace",
              }}>
                S:{fmtSentiment(rec.true_sentiment)}
              </div>
            )}
            <div style={{ fontSize: '8px', letterSpacing: '1.5px', color: '#2a4d7a' }}>
              US EQUITIES
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── EquityTile ──────────────────────────────────────────
function EquityTile({
  record, width = 100, height = 100, x, y
}: {
  record: LiveRecord
  width?: number
  height?: number
  x?: number
  y?: number
}) {
  const [hover, setHover] = useState(false)
  const isPos = x !== undefined && y !== undefined
  const lrSignal: number | null = record.true_sentiment !== null
    ? (record.true_sentiment > 0.03 ? 0.6
      : record.true_sentiment < -0.03 ? 0.4
      : 0.5)
    : record.poly_up_probability
  const { ul, lr } = diagColors(record.ret_pct, lrSignal)
  const stockOverlay = `linear-gradient(135deg, ${ul} 50%, transparent 50%)`
  const polyOverlay = `linear-gradient(135deg, transparent 50%, ${lr} 50%)`
  
  return (
    <div 
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        position: isPos ? 'absolute' : 'relative',
        left: x,
        top: y,
        width,
        height,
        borderRadius: '3px',
        border: `1px solid ${hover ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.04)'}`,
        overflow: 'hidden',
        cursor: 'pointer',
        boxSizing: 'border-box'
      }}
    >
      <div style={{
        position: 'absolute',
        inset: 0,
        background: '#152237'
      }} />
      <div style={{
        position: 'absolute',
        inset: 0,
        background: stockOverlay
      }} />
      <div style={{
        position: 'absolute',
        inset: 0,
        background: polyOverlay
      }} />
      <div style={{
        position: 'absolute',
        left: '50%',
        top: '-16%',
        width: '1px',
        height: '132%',
        background: hover ? 'rgba(226,232,240,0.34)' : 'rgba(226,232,240,0.2)',
        transform: 'rotate(45deg)',
        transformOrigin: 'center',
        zIndex: 1
      }} />
      
      <div style={{
        position: 'absolute',
        inset: 0,
        zIndex: 2,
        padding: '10px 10px 8px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        pointerEvents: 'none'
      }}>
        {height >= 60 ? (
          <>
            <div>
              <div style={{ fontSize: '15px', fontWeight: 500, letterSpacing: '1px', color: '#f1f5f9' }}>
                {record.ticker}
              </div>
              <div style={{ fontSize: '12px', color: retColor(record.ret_pct) }}>
                {fmtRet(record.ret_pct)}
              </div>
              {height > 80 && (
                <div style={{ fontSize: '9px', color: 'rgba(255,255,255,0.35)', marginTop: '2px' }}>
                  ${fmtPrice(record.last_close)}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
              <div>
                {(record.vol_ratio !== null && record.vol_ratio > 1.5) && (
                  <div style={{
                    background: '#0e2814',
                    color: '#4ade80',
                    border: '1px solid #1a6b3a',
                    fontSize: '9px',
                    padding: '2px 4px',
                    borderRadius: '2px'
                  }}>
                    {`VOL ${record.vol_ratio.toFixed(1)}×`}
                  </div>
                )}
              </div>
            </div>

            <div style={{
              position: 'absolute', bottom: 0, left: 0, right: 0,
              padding: '4px 8px 6px',
              display: 'flex', flexDirection: 'column', gap: '2px',
            }}>
              <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <span style={{
                  fontSize: '7px', letterSpacing: '0.5px',
                  color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase',
                }}>
                  Poly up
                </span>
                <span style={{
                  fontSize: '10px', fontWeight: 500,
                  fontFamily: "'Courier New', monospace",
                  color: polyColor(record.poly_up_probability),
                }}>
                  {fmtProb(record.poly_up_probability)}
                </span>
              </div>

              <div
                title="avg Polymarket probability minus Black-Scholes fair value"
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}
              >
                <span style={{
                  fontSize: '7px', letterSpacing: '0.5px',
                  color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase',
                }}>
                  Signal
                </span>
                <span style={{
                  fontSize: '10px', fontWeight: 500,
                  fontFamily: "'Courier New', monospace",
                  color: sentimentColor(record.true_sentiment),
                }}>
                  {fmtSentiment(record.true_sentiment)}
                </span>
              </div>
            </div>
          </>
        ) : (
          <div style={{ fontSize: '15px', fontWeight: 500, letterSpacing: '1px', color: '#f1f5f9' }}>
            {record.ticker}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── RightTile ──────────────────────────────────────────
function RightTile({ record }: { record: LiveRecord }) {
  const [hover, setHover] = useState(false)
  const stockOverlay =
    record.ret_pct !== null && record.ret_pct > 0.1
      ? 'linear-gradient(135deg, rgba(34,197,94,0.28) 50%, transparent 50%)'
      : record.ret_pct !== null && record.ret_pct < -0.1
        ? 'linear-gradient(135deg, rgba(239,68,68,0.3) 50%, transparent 50%)'
        : 'linear-gradient(135deg, rgba(100,116,139,0.12) 50%, transparent 50%)'
  const polyOverlay =
    record.poly_up_probability !== null && record.poly_up_probability > 0.55
      ? 'linear-gradient(135deg, transparent 50%, rgba(34,197,94,0.24) 50%)'
      : record.poly_up_probability !== null && record.poly_up_probability < 0.45
        ? 'linear-gradient(135deg, transparent 50%, rgba(239,68,68,0.28) 50%)'
        : 'linear-gradient(135deg, transparent 50%, rgba(100,116,139,0.1) 50%)'

  const dateStr = record.poly_target_date ? (() => {
    const d = new Date(record.poly_target_date)
    return isNaN(d.getTime()) ? '' : `${d.toLocaleString('en-US', {month: 'short'})} ${d.getDate()}`
  })() : ''

  return (
    <div 
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        minHeight: '72px',
        borderRadius: '3px',
        border: `1px solid ${hover ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.04)'}`,
        overflow: 'hidden',
        cursor: 'pointer',
        position: 'relative',
        boxSizing: 'border-box'
      }}
    >
      <div style={{
        position: 'absolute', inset: 0,
        background: '#152237'
      }} />
      <div style={{
        position: 'absolute', inset: 0,
        background: stockOverlay
      }} />
      <div style={{
        position: 'absolute', inset: 0,
        background: polyOverlay
      }} />
      <div style={{
        position: 'absolute',
        left: '50%',
        top: '-22%',
        width: '1px',
        height: '144%',
        background: hover ? 'rgba(226,232,240,0.34)' : 'rgba(226,232,240,0.2)',
        transform: 'rotate(45deg)',
        transformOrigin: 'center',
        zIndex: 1
      }} />
      
      <div style={{
        position: 'absolute', inset: 0, zIndex: 2,
        padding: '7px 8px',
        display: 'flex', flexDirection: 'column', justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '9px', fontWeight: 500, color: '#cbd5e1', letterSpacing: '0.5px' }}>
            {record.label || record.ticker}
          </span>
          <span style={{ fontSize: '7px', color: 'rgba(255,255,255,0.25)' }}>
            {dateStr}
          </span>
        </div>
        
        <div>
          <div style={{ fontSize: '11px', color: retColor(record.ret_pct) }}>
            {fmtRet(record.ret_pct)}
          </div>
          {record.last_close !== null && (
            <div style={{ fontSize: '13px', color: '#f1f5f9', marginTop: '4px' }}>
              {fmtPrice(record.last_close)}
            </div>
          )}
        </div>

        <div>
          <span style={{ fontSize: '8px', fontWeight: 500, color: polyColor(record.poly_up_probability), letterSpacing: '0.5px' }}>
            Poly up {fmtProb(record.poly_up_probability)}
          </span>
        </div>
      </div>
    </div>
  )
}

// ─── RightPanel ──────────────────────────────────────────
function getTimingText(targetDateStr: string | null): string {
  if (!targetDateStr) return ''
  const t = new Date(targetDateStr).getTime()
  if (isNaN(t)) return ''
  const diff = t - Date.now()
  if (diff <= 0) return ''
  const totalMins = Math.floor(diff / 60000)
  const d = Math.floor(totalMins / 1440)
  const h = Math.floor((totalMins % 1440) / 60)
  const m = totalMins % 60
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}min`
}

function Section({ title, color, records }: { title: string, color: string, records: LiveRecord[] }) {
  if (records.length === 0) return null
  
  const timingText = getTimingText(records[0]?.poly_target_date)

  return (
    <div style={{ marginBottom: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '5px', height: '5px', borderRadius: '50%', background: color }} />
          <span style={{ fontSize: '9px', letterSpacing: '2px', color: '#475569', textTransform: 'uppercase' }}>
            {title}
          </span>
        </div>
        {timingText && (
            <span style={{ fontSize: '8px', color: '#2a4d7a', letterSpacing: '0.5px' }}>
            {timingText}
          </span>
        )}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '2px' }}>
        {records.map(r => <RightTile key={r.ticker} record={r} />)}
      </div>
    </div>
  )
}

function RightPanel({ records }: { records: LiveRecord[] }) {
  const indices = records.filter(r => r.category === 'Indices')
  const crypto = records.filter(r => r.category === 'Crypto')
  const commodities = records.filter(r => r.category === 'Commodities')

  return (
    <div style={{ padding: '10px 10px 10px 0', display: 'flex', flexDirection: 'column' }}>
      <Section title="Indices" color="#38bdf8" records={indices} />
      <Section title="Crypto" color="#f59e0b" records={crypto} />
      <Section title="Commodities" color="#a78bfa" records={commodities} />
    </div>
  )
}

export default function LivePage() {
  const EQUITY_MIN_CAP = 50_000_000_000
  const [data, setData] = useState<LiveRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshIn, setRefreshIn] = useState(10)

  useEffect(() => {
    let mounted = true
    
    const fetchData = async () => {
      setLoading(true)
      try {
        const records = await fetchLive()
        if (mounted && records.length > 0) {
          setData(records)
        }
      } catch (e) {
        console.error(e)
      } finally {
        if (mounted) {
          setLoading(false)
          setRefreshIn(10)
        }
      }
    }

    fetchData()
    const fetchInterval = setInterval(fetchData, 10000)
    const tickInterval = setInterval(() => {
      setRefreshIn(prev => Math.max(0, prev - 1))
    }, 1000)

    return () => {
      mounted = false
      clearInterval(fetchInterval)
      clearInterval(tickInterval)
    }
  }, [])

  if (loading && data.length === 0) {
    return (
      <div style={{
        background: 'var(--bg)', minHeight: '100vh', display: 'flex', 
        alignItems: 'center', justifyContent: 'center',
        fontFamily: "'Courier New', monospace", fontSize: '14px', color: '#4a6080'
      }}>
        Warming up
        <style>{`
          @keyframes blink { 0% { opacity: .2; } 20% { opacity: 1; } 100% { opacity: .2; } }
          span.dot { animation: blink 1.4s infinite reverse; animation-fill-mode: both; }
          span.dot:nth-child(2) { animation-delay: .2s; }
          span.dot:nth-child(3) { animation-delay: .4s; }
        `}</style>
        <span className="dot">.</span><span className="dot">.</span><span className="dot">.</span>
      </div>
    )
  }

  const equityRecords = data.filter(d => d.category === 'US Equities')
    .sort((a, b) => (b.market_cap ?? 0) - (a.market_cap ?? 0))
  const nonEquityRecords = data.filter(d => d.category !== 'US Equities')
  const equityCount = equityRecords.length

  const treeData = equityRecords.map(r => ({
    name: r.ticker,
    value: Math.max(r.market_cap ?? EQUITY_MIN_CAP, EQUITY_MIN_CAP),
    record: r
  }))

  const renderEquityContent = (props: any) => {
    const { x, y, width, height, record } = props
    if (!record || width === undefined || height === undefined) return <g />
    return (
      <foreignObject x={x} y={y} width={width} height={height}>
        <EquityTile record={record} x={0} y={0} width={width} height={height} />
      </foreignObject>
    )
  }

  return (
    <div style={{ background: 'var(--bg)', minHeight: '100vh', fontFamily: "'Courier New', monospace" }}>
      <Banner records={equityRecords} />
      
      <div style={{
        padding: '10px 16px 6px',
        borderBottom: '1px solid #0f1e30',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: '15px', fontWeight: 500, color: '#f1f5f9' }}>
            Yahoo + Polymarket Dashboard
          </span>
          <span style={{ fontSize: '9px', color: '#4a6080', letterSpacing: '1.5px', textTransform: 'uppercase' }}>
            Stocks · Indices · Crypto · Commodities
          </span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px', color: '#475569' }}>
          {loading ? (
            <div style={{ width: '8px', height: '8px', border: '1px solid #4a6080', borderRadius: '50%', borderTopColor: '#f1f5f9', animation: 'spin 1s linear infinite' }} />
          ) : (
            <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#22c55e', animation: 'pulse 2s infinite' }} />
          )}
          <style>{`
            @keyframes spin { 100% { transform: rotate(360deg); } }
            @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
          `}</style>
          <span style={{ color: '#22c55e', fontWeight: 'bold' }}>Live</span>
          <span>{new Date().toISOString().split('T')[0]}</span>
          <span>·</span>
          <span>next refresh {refreshIn}s</span>
        </div>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 0.62fr',
        gap: '1px',
        background: '#0f1e30',
        margin: '10px 12px',
        borderRadius: '6px',
        overflow: 'visible'
      }}>
        <div style={{ background: 'var(--bg)', padding: '10px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
            <div style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#38bdf8' }} />
            <span style={{ fontSize: '9px', letterSpacing: '2px', color: '#475569', textTransform: 'uppercase' }}>Stocks</span>
            <span style={{ fontSize: '8px', color: '#4a6080', marginLeft: 'auto' }}>sized by market cap</span>
          </div>
          
          <div style={{ width: '100%', height: '480px', overflow: 'visible' }}>
            <ResponsiveContainer width="100%" height="100%">
              <Treemap
                data={treeData}
                dataKey="value"
                content={renderEquityContent}
                isAnimationActive={false}
              />
            </ResponsiveContainer>
          </div>

          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between',
            alignItems: 'center',
            borderTop: '1px solid #0f1e30',
            paddingTop: '6px',
            marginTop: '8px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{
                width: '10px',
                height: '10px',
                background: '#152237',
                borderRadius: '1px',
                position: 'relative',
                overflow: 'hidden'
              }}>
                <div style={{
                  position: 'absolute',
                  inset: 0,
                  background: 'linear-gradient(135deg, rgba(34,197,94,0.32) 50%, transparent 50%)'
                }} />
                <div style={{
                  position: 'absolute',
                  inset: 0,
                  background: 'linear-gradient(135deg, transparent 50%, rgba(239,68,68,0.3) 50%)'
                }} />
                <div style={{
                  position: 'absolute',
                  left: '50%',
                  top: '-24%',
                  width: '1px',
                  height: '150%',
                  background: 'rgba(226,232,240,0.4)',
                  transform: 'rotate(45deg)',
                  transformOrigin: 'center'
                }} />
              </div>
              <span style={{ fontSize: '8px', color: '#4a6080', letterSpacing: '0.5px' }}>
                {equityCount} live stocks · upper-left Yahoo return / lower-right Polymarket probability
              </span>
            </div>
            
            <div style={{ display: 'flex', gap: '12px' }}>
              {[
                { label: 'Up', color: '#0a3d1f' },
                { label: 'Down', color: '#3d0a0a' },
                { label: 'Flat', color: '#1a2030' }
              ].map(item => (
                <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <div style={{ width: '8px', height: '8px', background: item.color, borderRadius: '1px' }} />
                  <span style={{ fontSize: '8px', color: '#4a6080' }}>{item.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div style={{ background: 'var(--bg)' }}>
          <RightPanel records={nonEquityRecords} />
        </div>
      </div>
    </div>
  )
}

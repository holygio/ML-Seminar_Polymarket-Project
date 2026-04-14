import { fetchAsset, fetchAssetPreopen, fetchHeatmap } from '@/lib'
import { ALL_TICKERS, type Ticker } from '@/lib'
import AssetPageHeader from '@/components/asset/AssetPageHeader'
import CombinedChart from '@/components/asset/CombinedChart'
import TrueSentimentPanel from '@/components/asset/TrueSentimentPanel'
import AlignmentGrid from '@/components/asset/AlignmentGrid'
import PreOpenTimeline from '@/components/asset/PreOpenTimeline'
import SignalQualityPanel from '@/components/asset/SignalQualityPanel'
import ModelSnapshot from '@/components/asset/ModelSnapshot'
import { notFound } from 'next/navigation'

export function generateStaticParams() {
  return ALL_TICKERS.map(t => ({ ticker: t }))
}

export default async function AssetPage({
  params,
  searchParams,
}: {
  params: Promise<{ ticker: string }>
  searchParams: Promise<{ days?: string }>
}) {
  const { ticker } = await params
  const { days: daysParam } = await searchParams
  const upperTicker = ticker.toUpperCase()
  const requestedDays = Math.min(60, Math.max(1, Number.parseInt(daysParam ?? '60', 10) || 60))

  if (!ALL_TICKERS.includes(upperTicker as Ticker)) {
    notFound()
  }

  const [dataResult, preopenResult, heatmapResult] = await Promise.allSettled([
    fetchAsset(upperTicker, requestedDays),
    fetchAssetPreopen(upperTicker),
    fetchHeatmap(requestedDays)
  ])

  if (dataResult.status !== 'fulfilled') {
    const error = dataResult.reason as Error
    return (
      <div style={{ color: '#ef4444', padding: '40px' }}>
        Failed to load {upperTicker}: {error.message}
      </div>
    )
  }

  const data = dataResult.value
  const preopenData = preopenResult.status === 'fulfilled'
    ? preopenResult.value.preopen_series
    : []
  const heatmapData = heatmapResult.status === 'fulfilled'
    ? heatmapResult.value.data.filter(d => d.ticker === upperTicker)
    : []

  const len = data.stock_series.length
  const latestReturn = len > 1 && data.stock_series[len - 1].close && data.stock_series[len - 2].close
    ? (((data.stock_series[len - 1].close!) / (data.stock_series[len - 2].close!) - 1) * 100).toFixed(2)
    : null
  
  const returnStr = latestReturn !== null ? (Number(latestReturn) >= 0 ? `+${latestReturn}%` : `${latestReturn}%`) : null
  const latestProb = data.probability_series.length > 0 
    ? data.probability_series[data.probability_series.length - 1].price_up
    : null
  const latestClose = len > 0 ? data.stock_series[len - 1].close : null
  const latestTimestamp = len > 0 ? data.stock_series[len - 1].timestamp : null

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '32px' }}>
      <AssetPageHeader
        ticker={upperTicker as Ticker}
        days={requestedDays}
        availableTickers={ALL_TICKERS}
        lastClose={latestClose}
        return1D={returnStr}
        polyProb={latestProb}
        latestDate={latestTimestamp}
      />
      
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 340px', gap: '32px' }}>
        {/* Left Column */}
        <div style={{ display: 'flex', flexDirection: 'column', borderRight: '1px solid #1a2840', paddingRight: '32px' }}>
          <CombinedChart
            days={requestedDays}
            stock={data.stock_series}
            prob={data.probability_series}
          />
          
          <TrueSentimentPanel tsData={data.true_sentiment_series} />
          <AlignmentGrid data={heatmapData} maxDays={requestedDays} />
        </div>
        
        {/* Right Column */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <SignalQualityPanel signal={data.latest_signal} />
          <PreOpenTimeline data={preopenData} />
          <ModelSnapshot signal={data.latest_signal} ticker={upperTicker} days={requestedDays} />
        </div>
      </div>
    </div>
  )
}

import { fetchAsset, fetchAssetPreopen } from '@/lib/api'
import { ALL_TICKERS } from '@/lib/types'
import AssetHeader from '@/components/asset/AssetHeader'
import ProbabilityChart from '@/components/asset/ProbabilityChart'
import SignalMetricsBlock from '@/components/asset/SignalMetricsBlock'
import StockChart from '@/components/asset/StockChart'
import TrueSentimentChart from '@/components/asset/TrueSentimentChart'

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
  const { days: d } = await searchParams
  const days = parseInt(d ?? '1', 10)
  const upperTicker = ticker.toUpperCase()

  const [dataResult, preopenResult] = await Promise.allSettled([
    fetchAsset(upperTicker, days),
    fetchAssetPreopen(upperTicker),
  ])

  if (dataResult.status !== 'fulfilled') {
    const error = dataResult.reason as Error
    return (
      <div style={{ color: 'var(--red)', padding: '40px' }}>
        Failed to load {upperTicker}: {error.message}
      </div>
    )
  }

  const data = dataResult.value
  const preopenData = preopenResult.status === 'fulfilled'
    ? preopenResult.value.preopen_series
    : []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <AssetHeader
        ticker={upperTicker}
        overnightChange={data.latest_signal?.overnight_prob_change ?? null}
        signalDirection={data.latest_signal?.signal_direction ?? null}
        impliedProb={data.latest_signal?.pre_open_implied_prob ?? null}
        days={days}
      />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
        <ProbabilityChart data={data.probability_series} preopenData={preopenData} />
        <StockChart data={data.stock_series} />
      </div>
      <TrueSentimentChart data={data.true_sentiment_series} />
      <SignalMetricsBlock signal={data.latest_signal} />
    </div>
  )
}

import type { HealthStatus, SignalToday, AssetDetail, HeatmapResponse, ProbabilityPoint, LiveRecord, LiveResponse } from './types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: 'no-store' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `API error ${res.status} on ${path}`)
  }
  return res.json() as Promise<T>
}

export const fetchHealth = () =>
  apiFetch<HealthStatus>('/health')

export const fetchSignalsToday = () =>
  apiFetch<{ data: SignalToday[]; count: number }>('/api/signals/today')

export const fetchAsset = (ticker: string, days = 1) =>
  apiFetch<AssetDetail>(`/api/asset/${ticker}?days=${days}`)

export const fetchAssetPreopen = (ticker: string) =>
  apiFetch<{ ticker: string; preopen_series: ProbabilityPoint[] }>(`/api/asset/${ticker}/preopen`)

export const fetchHeatmap = (days = 30) =>
  apiFetch<HeatmapResponse>(`/api/heatmap?days=${days}`)

export async function fetchLive(): Promise<LiveRecord[]> {
  const base = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
  const res = await fetch(`${base}/api/live`, { cache: 'no-store' })
  if (!res.ok) return []   // covers 503 warming_up
  const json: LiveResponse = await res.json()
  return json.data ?? []
}

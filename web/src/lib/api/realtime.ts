/**
 * cQuant API — Real-time quotes domain.
 */

import { api, type RequestConfig } from './client'

// ── Types (not yet in types/) ────────────────────────────────────────────────

export interface RealtimeQuote {
  asset_id: string
  symbol: string
  price: number
  open: number
  high: number
  low: number
  close: number
  prev_close: number
  volume: number
  amount: number
  bid1: number
  ask1: number
  bid1_vol: number
  ask1_vol: number
  change: number
  change_pct: number
  timestamp: string
}

// ── API ────────────────────────────────────────────────────────────────────

export const realtimeApi = {
  quote: (symbol: string, config?: RequestConfig) =>
    api.get<RealtimeQuote>(`/live/quote/${symbol}`, config),

  quotes: (symbols: string[], config?: RequestConfig) =>
    api.get<{
      items: Record<string, RealtimeQuote>
      count: number
      timestamp: string
    }>(`/live/quotes?symbols=${symbols.join(',')}`, config),

  market: (limit = 20, config?: RequestConfig) =>
    api.get<{
      items: Record<string, RealtimeQuote>
      count: number
      timestamp: string
    }>(`/live/market?limit=${limit}`, config),

  streamUrl: (symbols: string[], interval = 5) => {
    const params = new URLSearchParams({
      symbols: symbols.join(','),
      interval: String(interval),
    })
    return `/api/v1/live/stream?${params}`
  },
}

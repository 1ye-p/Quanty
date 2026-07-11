/**
 * cQuant API — Market data domain.
 */

import { api, type RequestConfig } from './client'

// ── Types ────────────────────────────────────────────────────────────────────

export interface OHLCV {
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface PriceStats {
  latest_price: number
  change_pct: number
  high_52w: number
  low_52w: number
  avg_volume: number
}

export interface Asset {
  asset_id: string
  name: string
  exchange: string
}

export interface PricesResponse {
  asset_id: string
  prices: OHLCV[]
  stats: PriceStats
}

// ── API ──────────────────────────────────────────────────────────────────────

export const marketApi = {
  getPrices: (assetId: string, start: string, end: string, period: string = 'daily', config?: RequestConfig) =>
    api.get<PricesResponse>(
      `/market/prices?asset_id=${encodeURIComponent(assetId)}&start=${start}&end=${end}&period=${period}`,
      config,
    ),
  searchAssets: (q: string, limit = 20, config?: RequestConfig) =>
    api.get<{ assets: Asset[] }>(
      `/market/assets?q=${encodeURIComponent(q)}&limit=${limit}`,
      config,
    ),
}

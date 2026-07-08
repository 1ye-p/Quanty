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

export interface PricesResponse {
  asset_id: string
  prices: OHLCV[]
  stats: PriceStats
}

// ── API ──────────────────────────────────────────────────────────────────────

export const marketApi = {
  getPrices: (assetId: string, start: string, end: string, config?: RequestConfig) =>
    api.get<PricesResponse>(
      `/market/prices?asset_id=${encodeURIComponent(assetId)}&start=${start}&end=${end}`,
      config,
    ),
}

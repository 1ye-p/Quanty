/**
 * cQuant API — Indicators domain.
 *
 * Technical indicator catalog, category listing, and on-the-fly computation.
 */

import { api, type RequestConfig } from './client'

// ── Types ────────────────────────────────────────────────────────────────────

export interface IndicatorParam {
  name: string
  type: string
  default: number
}

export interface IndicatorInfo {
  name: string
  category: string
  description: string
  params: IndicatorParam[]
}

export interface IndicatorCategories {
  categories: Record<string, { count: number; indicators: string[] }>
}

// ── API ──────────────────────────────────────────────────────────────────────

export const indicatorsApi = {
  /** List all indicators, optionally filtered by category. */
  list: (category?: string, config?: RequestConfig) => {
    const qs = category ? `?category=${encodeURIComponent(category)}` : ''
    return api.get<{ indicators: IndicatorInfo[]; total: number }>(
      `/indicators${qs}`,
      config,
    )
  },

  /** Get indicator categories with counts. */
  categories: (config?: RequestConfig) =>
    api.get<IndicatorCategories>('/indicators/categories', config),

  /**
   * Compute one or more indicators on provided OHLCV data.
   *
   * @param body.data - Array of OHLCV rows (date, open, high, low, close, volume)
   * @param body.indicators - Indicators to compute with optional param overrides
   */
  compute: (
    body: {
      data: Record<string, unknown>[]
      indicators: { name: string; params?: Record<string, number> }[]
    },
    config?: RequestConfig,
  ) =>
    api.post<{ columns: string[]; rows: Record<string, unknown>[] }>(
      '/indicators/compute',
      body,
      config,
    ),
}

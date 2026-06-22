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

export interface EvaluateConditionResponse {
  signals: boolean[]
  signal_dates: string[]
  hit_count: number
  total_bars: number
  hit_rate: number
}

export interface ConditionPreviewResponse {
  signals: boolean[]
  buy_signals: number[]
  total_signals: number
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

  /**
   * Evaluate a condition DSL string against historical data.
   *
   * @param body.condition_dsl - DSL expression like "SMA(close, 20) > SMA(close, 50)"
   * @param body.data - Array of OHLCV rows
   * @returns Signal statistics including hit count and hit rate
   */
  evaluateCondition: (
    body: { condition_dsl: string; data: Record<string, unknown>[] },
    config?: RequestConfig,
  ) =>
    api.post<EvaluateConditionResponse>(
      '/indicators/evaluate-condition',
      body,
      config,
    ),

  /**
   * Preview condition signals on data.
   *
   * @param body.condition_dsl - DSL expression
   * @param body.data - Array of OHLCV rows
   * @returns Signal positions and counts
   */
  conditionPreview: (
    body: { condition_dsl: string; data: Record<string, unknown>[] },
    config?: RequestConfig,
  ) =>
    api.post<ConditionPreviewResponse>(
      '/indicators/condition-preview',
      body,
      config,
    ),
}

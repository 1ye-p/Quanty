/**
 * cQuant API — Portfolio Optimization domain.
 */

import { api, type RequestConfig } from './client'

// ── Types (not yet in types/) ────────────────────────────────────────────────

export interface SectorLimit {
  min_weight: number
  max_weight: number
}

export interface FactorExposureLimit {
  min_exposure: number
  max_exposure: number
}

export interface ConstraintConfig {
  long_only?: boolean
  max_weight?: number
  min_weight?: number
  min_weights?: Record<string, number>
  max_weights?: Record<string, number>
  max_turnover?: number | null
  turnover_penalty?: number
  current_weights?: Record<string, number>
  target_return?: number | null
  sector_map?: Record<string, string>
  sector_limits?: Record<string, SectorLimit>
  factor_loadings?: Record<string, Record<string, number>>
  factor_limits?: Record<string, FactorExposureLimit>
  max_tracking_error?: number | null
  benchmark_weights?: Record<string, number>
  exclude_assets?: string[]
  exclude_st?: boolean
  st_assets?: string[]
  exclude_suspended?: boolean
  suspended_assets?: string[]
}

export interface ViewSpec {
  asset: string
  against?: string
  expected_return: number
  confidence: number
}

export interface OptimizeRequest {
  expected_returns: Record<string, number>
  covariance: Record<string, Record<string, number>>
  optimizer?: 'mean_variance' | 'risk_parity' | 'cost_aware' | 'black_litterman'
  constraints?: Record<string, unknown>
  constraint_config?: ConstraintConfig
  risk_free_rate?: number
  long_only?: boolean
  cost_rate?: number
  turnover_penalty?: number
  current_weights?: Record<string, number>
  views?: ViewSpec[]
  tau?: number
  market_weights?: Record<string, number>
  risk_aversion?: number
}

export interface OptimizeResult {
  weights: Record<string, number>
  expected_return: number
  expected_volatility: number
  sharpe_ratio: number
  metadata: Record<string, unknown>
}

export interface FrontierPoint {
  expected_return: number
  volatility: number
  sharpe: number
  weights: Record<string, number>
}

export interface FrontierResult {
  points: FrontierPoint[]
  min_variance_point: FrontierPoint
  max_sharpe_point: FrontierPoint
  individual_assets: { asset: string; expected_return: number; volatility: number }[]
}

export interface CovarianceRequest {
  asset_ids: string[]
  as_of_date?: string
  method?: 'historical' | 'ewma' | 'ledoit_wolf'
  window?: number
  halflife?: number
}

export interface CovarianceResult {
  covariance: Record<string, Record<string, number>>
  assets: string[]
  method: string
  as_of_date: string
}

// ── API ──────────────────────────────────────────────────────────────────────

export const optimizeApi = {
  optimize: (body: OptimizeRequest, config?: RequestConfig) =>
    api.post<OptimizeResult>('/optimize', body, config),

  covariance: (body: CovarianceRequest, config?: RequestConfig) =>
    api.post<CovarianceResult>('/optimize/covariance', body, config),

  getFrontier: (body: {
    assets: string[]
    constraints?: Record<string, unknown>
    n_points?: number
    risk_free_rate?: number
  }, config?: RequestConfig) =>
    api.post<FrontierResult>('/optimize/frontier', body, config),
}

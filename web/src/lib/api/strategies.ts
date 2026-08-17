/**
 * cQuant API — Strategies domain.
 */

import { api, type RequestConfig } from './client'
import type {
  Strategy,
  StrategyCreateParams,
  StrategyVersion,
  OptimizationReport,
} from '../types'

// ── API ──────────────────────────────────────────────────────────────────────

export const strategiesApi = {
  list: (config?: RequestConfig) =>
    api.get<{ items: Strategy[]; total: number }>('/strategies', config),

  get: (id: string, config?: RequestConfig) =>
    api.get<Strategy>(`/strategies/${id}`, config),

  create: (body: StrategyCreateParams, config?: RequestConfig) =>
    api.post('/strategies', body, config),

  update: (
    id: string,
    body: { config_text: string; config_format?: string },
    config?: RequestConfig,
  ) =>
    api.put(`/strategies/${id}`, body, config),

  delete: (id: string, config?: RequestConfig) =>
    api.delete(`/strategies/${id}`, config),

  versions: (strategyId: string, config?: RequestConfig) =>
    api.get<{ items: StrategyVersion[]; strategy_id: string }>(
      `/strategies/${strategyId}/versions`,
      config,
    ),

  rollback: (strategyId: string, versionId: string, config?: RequestConfig) =>
    api.post<{
      strategy_id: string
      status: string
      version_id: string
      summary: string
    }>(`/strategies/${strategyId}/rollback/${versionId}`, undefined, config),

  optimizationReport: (strategyId: string, config?: RequestConfig) =>
    api.get<OptimizationReport>(`/strategies/${strategyId}/optimization-report`, config),

  applyOptimization: (
    strategyId: string,
    body: { best_params: Record<string, unknown>; confirm: boolean; baseline_run_id?: string },
    config?: RequestConfig,
  ) =>
    api.post<{
      strategy_id: string
      status: string
      version_id: string
      applied_params: Record<string, unknown>
      baseline_run_id: string | null
    }>(`/strategies/${strategyId}/apply-optimization`, body, config),
}

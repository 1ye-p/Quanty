/**
 * cQuant API — Strategies domain.
 */

import { api, type RequestConfig } from './client'
import type {
  Strategy,
  StrategyCreateParams,
  StrategyVersion,
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
}

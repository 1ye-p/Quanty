/**
 * cQuant API — Factors domain.
 */

import { api, type RequestConfig } from './client'
import type {
  FactorDefinition,
  ICResult,
  FactorCorrelation,
  CustomFactor,
  ICStatusItem,
} from '../types'

// ── API ──────────────────────────────────────────────────────────────────────

export const factorsApi = {
  definitions: (config?: RequestConfig) =>
    api.get<{ items: FactorDefinition[]; total: number }>('/factors/definitions', config),

  versions: (config?: RequestConfig) =>
    api.get<{
      items: Array<{
        feature_set_version: string
        start_date: string
        end_date: string
        row_count: number
      }>
    }>('/factors/versions', config),

  computeIC: (
    body: { factor_name: string; feature_set_version: string; horizon_days?: number },
    config?: RequestConfig,
  ) =>
    api.post<{ job_id: string; status: string }>(
      '/factors/analytics/compute',
      body,
      config,
    ),

  computeICMatrix: (
    body: { factor_names: string[]; feature_set_version: string; horizon_days?: number },
    config?: RequestConfig,
  ) =>
    api.post<{ job_id: string; status: string }>(
      '/factors/analytics/matrix',
      body,
      config,
    ),

  icJob: (jobId: string, config?: RequestConfig) =>
    api.get<ICResult>(`/factors/analytics/${jobId}`, config),

  computeQuintiles: (
    body: {
      factor_name: string
      feature_set_version: string
      horizon_days?: number
      start_date?: string
      end_date?: string
      n_groups?: number
    },
    config?: RequestConfig,
  ) =>
    api.post<{
      factor_name: string
      horizon_days: number
      n_groups: number
      groups: { quintile: string; mean_return: number; std_return: number; count: number }[]
      cumulative_returns: { trade_date: string; q1: number; q2: number; q3: number; q4: number; q5: number }[]
    }>('/factors/analytics/quintiles', body, config),

  computeFactorCorrelation: (
    body: {
      factor_names: string[]
      feature_set_version: string
      start_date?: string
      end_date?: string
    },
    config?: RequestConfig,
  ) =>
    api.post<FactorCorrelation>(
      '/factors/analytics/factor-correlation',
      body,
      config,
    ),

  icStatus: (
    params: { feature_set_version?: string; threshold?: number; window_days?: number },
    config?: RequestConfig,
  ) => {
    const qs = new URLSearchParams()
    if (params.feature_set_version) qs.set('feature_set_version', params.feature_set_version)
    if (params.threshold != null) qs.set('threshold', String(params.threshold))
    if (params.window_days != null) qs.set('window_days', String(params.window_days))
    return api.get<{
      items: ICStatusItem[]
      threshold: number
      window_days: number
      feature_set_version: string
    }>(`/factors/ic-status?${qs}`, config)
  },

  // Custom factors (also available as nested `custom`)
  custom: {
    list: (config?: RequestConfig) =>
      api.get<{ items: CustomFactor[] }>('/factors/custom', config),

    create: (
      body: { name: string; expression: string; description?: string; expression_type?: string },
      config?: RequestConfig,
    ) =>
      api.post<{ factor_id: string; name: string; status: string }>(
        '/factors/custom',
        body,
        config,
      ),

    delete: (factorId: string, config?: RequestConfig) =>
      api.delete<{ factor_id: string; status: string }>(
        `/factors/custom/${factorId}`,
        config,
      ),

    preview: (
      body: { expression: string; feature_set_version?: string },
      config?: RequestConfig,
    ) =>
      api.post<{
        valid: boolean
        error: string | null
        preview: { asset_id: string; trade_date: string; value: number | null }[]
      }>('/factors/custom/preview', body, config),
  },

  // DSL (also available as nested `dsl`)
  dsl: {
    functions: (config?: RequestConfig) =>
      api.get<{
        functions: { name: string; minArgs: number; maxArgs: number; description: string }[]
        columns: string[]
        examples: { name: string; expression: string }[]
      }>('/factors/dsl/functions', config),
  },
}

// ── Backward-compatible aliases ──────────────────────────────────────────────
// These match the names exported from the old monolithic api.ts.

/** @deprecated Use `factorsApi` with its nested `custom` property instead. */
export const customFactorApi = factorsApi.custom

/** @deprecated Use `factorsApi` with its nested `dsl` property instead. */
export const dslApi = factorsApi.dsl

/** @deprecated Use `factorsApi` instead. */
export const factorAnalyticsApi = factorsApi

/**
 * cQuant API — Datasets domain.
 */

import { api, type RequestConfig } from './client'

// ── Types (not yet in types/) ────────────────────────────────────────────────

export interface DatasetVersion {
  version_id: string
  dataset_name: string
  frequency: string
  start_date: string
  end_date: string
  asset_count: number | null
  row_count: number | null
  source: string
  created_at: string
  is_current: boolean
}

// ── API ────────────────────────────────────────────────────────────────────

export const datasetsApi = {
  list: (limit = 50, config?: RequestConfig) =>
    api.get<{ items: DatasetVersion[]; total: number }>(`/datasets?limit=${limit}`, config),

  get: (id: string, config?: RequestConfig) =>
    api.get<DatasetVersion>(`/datasets/${id}`, config),

  universes: (config?: RequestConfig) =>
    api.get<{
      predefined: { id: string; name: string; description: string }[]
      available_assets: string[]
      total_assets: number
    }>('/datasets/universes', config),

  quality: (version = '', config?: RequestConfig) =>
    api.get<{
      version: string
      stats: {
        n_assets: number
        min_date: string
        max_date: string
        total_rows: number
        recent_assets: number
        null_rate: number
        outlier_count: number
      }
      daily_coverage: { trade_date: string; n_assets: number }[]
      bottom_assets: { asset_id: string; valid_days: number }[]
    }>(`/datasets/quality?version=${encodeURIComponent(version)}`, config),

  scheduleStatus: (config?: RequestConfig) =>
    api.get<{
      enabled: boolean
      last_run: string | null
      last_status: 'success' | 'error' | 'running' | null
      last_error: string | null
      next_run: string | null
      last_data_date: string | null
    }>('/datasets/schedule', config),

  triggerIngest: (config?: RequestConfig) =>
    api.post<{ status: string }>('/datasets/schedule/trigger', undefined, config),

  freshness: (config?: RequestConfig) =>
    api.get<{ last_updated: string | null; days_stale: number }>(
      '/datasets/freshness',
      config,
    ),
}

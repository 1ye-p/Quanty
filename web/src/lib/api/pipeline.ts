/**
 * cQuant API — Pipeline domain.
 */

import { api, type RequestConfig } from './client'

// ── Types (not yet in types/) ────────────────────────────────────────────────

export interface PipelineStage {
  status: string
  error?: string
  [key: string]: unknown
}

export interface PipelineStatusResponse {
  status: string
  detail?: string
  run_id?: string
  started_at?: string
  finished_at?: string
  duration_seconds?: number
  stages?: Record<string, PipelineStage>
}

// ── API ────────────────────────────────────────────────────────────────────

export const pipelineApi = {
  status: (config?: RequestConfig) =>
    api.get<PipelineStatusResponse>('/pipeline/status', config),

  run: (body?: { node_configs?: Record<string, Record<string, unknown>> }, config?: RequestConfig) =>
    api.post<{ status: string; detail?: string }>('/pipeline/run', body, config),
}

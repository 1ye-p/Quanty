/**
 * cQuant API — Scoring domain.
 */

import { api, type RequestConfig } from './client'

// ── Types (not yet in types/) ────────────────────────────────────────────────

export interface ScoringRun {
  run_id: string
  config_name: string
  feature_set_version?: string
  start_date?: string
  end_date?: string
  status: string
  created_at?: string
  completed_at?: string
}

export interface ScoringResult {
  trade_date: string
  asset_id: string
  score: number | null
  rank: number | null
}

export interface ScoringConfigBody {
  name: string
  factors: { factor_name: string; weight: number; direction: string }[]
  feature_set_version: string
  start_date: string
  end_date: string
  winsorize?: number[]
  fill_null?: string
}

// ── API ────────────────────────────────────────────────────────────────────

export const scoringApi = {
  run: (body: ScoringConfigBody, config?: RequestConfig) =>
    api.post<{ run_id: string; status: string }>('/scoring/run', body, config),

  getResult: (runId: string, offset = 0, limit = 50, tradeDate = '', config?: RequestConfig) =>
    api.get<{
      run: ScoringRun
      results: ScoringResult[]
      total: number
      offset: number
      limit: number
      score_distribution: { breakpoint?: number; count: number }[]
      available_dates: string[]
    }>(
      `/scoring/results/${runId}?offset=${offset}&limit=${limit}${tradeDate ? `&trade_date=${tradeDate}` : ''}`,
      config,
    ),

  listSnapshots: (limit = 20, config?: RequestConfig) =>
    api.get<{ items: ScoringRun[] }>(`/scoring/snapshots?limit=${limit}`, config),
}

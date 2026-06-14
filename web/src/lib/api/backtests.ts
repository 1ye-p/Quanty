/**
 * cQuant API — Backtests domain.
 */

import { api, type RequestConfig } from './client'
import type {
  Backtest,
  BacktestFill,
  BacktestCreateParams,
  BacktestResult,
  BacktestJobStatus,
  BacktestCompareRun,
  WalkForwardFold,
  WalkForwardConfig,
} from '../types'

// Re-export types for backward compatibility
export type { Backtest as BacktestRun, BacktestFill, WalkForwardConfig, WalkForwardFold }

// ── API ──────────────────────────────────────────────────────────────────────

export const backtestsApi = {
  list: (offset = 0, limit = 50, config?: RequestConfig) =>
    api.get<{ items: Backtest[]; total: number }>(
      `/backtests?offset=${offset}&limit=${limit}`,
      config,
    ),

  get: (id: string, config?: RequestConfig) =>
    api.get<Backtest>(`/backtests/${id}`, config),

  getAnalysis: (id: string, config?: RequestConfig) =>
    api.get<Record<string, unknown>>(`/backtests/${id}/analysis`, config),

  getRisk: (id: string, limit = 20, config?: RequestConfig) =>
    api.get<{ items: Record<string, unknown>[]; total: number }>(
      `/backtests/${id}/risk?limit=${limit}`,
      config,
    ),

  create: (body: BacktestCreateParams, config?: RequestConfig) =>
    api.post<BacktestResult>('/backtests', body, config),

  getFills: (id: string, offset = 0, limit = 50, config?: RequestConfig) =>
    api.get<{ items: BacktestFill[]; total: number; offset: number; limit: number }>(
      `/backtests/${id}/fills?offset=${offset}&limit=${limit}`,
      config,
    ),

  pollJob: (jobId: string, config?: RequestConfig) =>
    api.get<BacktestJobStatus>(`/backtests/jobs/${jobId}`, config),

  triggerAnalysis: (id: string, config?: RequestConfig) =>
    api.post<{ job_id: string; run_id: string; status: string }>(
      `/backtests/${id}/analyze`,
      undefined,
      config,
    ),

  compare: (runIds: string, config?: RequestConfig) =>
    api.get<{ runs: BacktestCompareRun[] }>(
      `/backtests/compare?run_ids=${encodeURIComponent(runIds)}`,
      config,
    ),

  getWalkForwardFolds: (id: string, config?: RequestConfig) =>
    api.get<{
      run_id: string
      n_folds: number
      folds: WalkForwardFold[]
      aggregated: Record<string, number>
    }>(`/backtests/${id}/walk-forward-folds`, config),

  getTca: (id: string, config?: RequestConfig) =>
    api.get<Record<string, unknown>>(`/backtests/${id}/tca`, config),

  getAttribution: (id: string, config?: RequestConfig) =>
    api.get<Record<string, unknown>>(`/backtests/${id}/attribution`, config),

  getRiskRolling: (id: string, window = 60, config?: RequestConfig) =>
    api.get<Record<string, unknown>>(
      `/backtests/${id}/risk-rolling?window=${window}`,
      config,
    ),

  getDrawdowns: (id: string, config?: RequestConfig) =>
    api.get<Record<string, unknown>>(`/backtests/${id}/drawdowns`, config),

  getDrawdownTimeseries: (id: string, config?: RequestConfig) =>
    api.get<Record<string, unknown>>(`/backtests/${id}/drawdown-timeseries`, config),

  getReturnDistribution: (id: string, bins = 50, config?: RequestConfig) =>
    api.get<Record<string, unknown>>(
      `/backtests/${id}/return-distribution?bins=${bins}`,
      config,
    ),

  getCorrelation: (id: string, window = 60, config?: RequestConfig) =>
    api.get<Record<string, unknown>>(
      `/backtests/${id}/correlation?window=${window}`,
      config,
    ),

  getFactorExposure: (id: string, window = 20, config?: RequestConfig) =>
    api.get<Record<string, unknown>>(
      `/backtests/${id}/factor-exposure?window=${window}`,
      config,
    ),

  getStressTest: (id: string, config?: RequestConfig) =>
    api.get<Record<string, unknown>>(`/backtests/${id}/stress-test`, config),

  getRiskContribution: (id: string, window = 60, config?: RequestConfig) =>
    api.get<Record<string, unknown>>(
      `/backtests/${id}/risk-contribution?window=${window}`,
      config,
    ),

  getCalendarAnalysis: (id: string, config?: RequestConfig) =>
    api.get<Record<string, unknown>>(`/backtests/${id}/calendar-analysis`, config),

  getTradeAnalysis: (id: string, config?: RequestConfig) =>
    api.get<Record<string, unknown>>(`/backtests/${id}/trade-analysis`, config),

  // Extended
  tearsheet: (id: string, config?: RequestConfig) =>
    api.get<Record<string, unknown>>(`/backtests/${id}/tearsheet`, config),

  validationWindows: (id: string, config?: RequestConfig) =>
    api.get<{ walk_forward: Record<string, unknown>[]; cpcv: Record<string, unknown>[] }>(
      `/backtests/${id}/validation-windows`,
      config,
    ),

  multipleTesting: (id: string, config?: RequestConfig) =>
    api.get<Record<string, Record<string, unknown>>>(
      `/backtests/${id}/multiple-testing`,
      config,
    ),
}

// ── Backward-compatible alias ───────────────────────────────────────────────

/** @deprecated Use `backtestsApi` which now includes tearsheet/validationWindows/multipleTesting. */
export const backtestExtApi = {
  tearsheet: backtestsApi.tearsheet,
  validationWindows: backtestsApi.validationWindows,
  multipleTesting: backtestsApi.multipleTesting,
}

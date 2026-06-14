/**
 * cQuant API — Live trading domain.
 */

import { api, type RequestConfig } from './client'

// ── Types (not yet in types/) ────────────────────────────────────────────────

export interface LiveDeployment {
  live_id: string
  backtest_run_id: string
  strategy_id: string
  initial_cash: number
  risk_mode: string
  status: string
  deployed_at: string
  stopped_at: string | null
  metrics: { sharpe?: number | null; max_drawdown?: number | null; cagr?: number | null }
}

export interface LiveStrategy {
  strategy_id: string
  last_run_id: string
  last_update: string
  status: string
}

export interface LiveExecution {
  execution_id: string
  live_id: string
  strategy_id: string
  order_id: string
  asset_id: string
  side: string
  qty: number
  filled_qty: number
  filled_price: number
  commission: number
  stamp_duty: number
  slippage: number
  total_cost: number
  status: string
  reject_reason: string
  executed_at: string
}

// ── API ────────────────────────────────────────────────────────────────────

export const liveApi = {
  strategies: (config?: RequestConfig) =>
    api.get<{ items: LiveStrategy[]; total: number; display_mode: string }>(
      '/live/strategies',
      config,
    ),

  pnl: (id: string, params?: Record<string, string>, config?: RequestConfig) => {
    const qs = params ? '?' + new URLSearchParams(params) : ''
    return api.get<{
      strategy_id: string
      run_id: string
      series: Record<string, unknown>[]
      display_mode: string
    }>(`/live/strategies/${id}/pnl${qs}`, config)
  },

  positions: (id: string, config?: RequestConfig) =>
    api.get<{ items: Record<string, unknown>[]; display_mode: string }>(
      `/live/strategies/${id}/positions`,
      config,
    ),

  risk: (id: string, config?: RequestConfig) =>
    api.get<{
      latest_snapshot: Record<string, unknown> | null
      history: Record<string, unknown>[]
      display_mode: string
    }>(`/live/strategies/${id}/risk`, config),

  deploy: (
    body: { backtest_run_id: string; initial_cash: number; risk_mode: string },
    config?: RequestConfig,
  ) =>
    api.post<{
      live_id: string
      strategy_id: string
      status: string
      deployed_at: string
    }>('/live/deploy', body, config),

  stopDeployed: (liveId: string, config?: RequestConfig) =>
    api.post<{ live_id: string; status: string }>(
      `/live/strategies/${liveId}/stop`,
      undefined,
      config,
    ),

  deployed: (config?: RequestConfig) =>
    api.get<{ items: LiveDeployment[] }>('/live/deployed', config),

  getExecutions: (liveId: string, limit = 50, offset = 0, config?: RequestConfig) =>
    api.get<{
      items: LiveExecution[]
      total: number
      live_id: string
      strategy_id: string
    }>(`/live/strategies/${liveId}/executions?limit=${limit}&offset=${offset}`, config),
}

/**
 * cQuant API — Risk Management domain.
 */

import { api, type RequestConfig } from './client'

// ── Types (not yet in types/) ────────────────────────────────────────────────

export interface PolicyParam {
  key: string
  type: string
  default: unknown
  description: string
}

export interface PolicyInfo {
  name: string
  description: string
  params: PolicyParam[]
}

export interface SizerInfo {
  name: string
  description: string
  params: PolicyParam[]
}

export interface RiskCheckRequest {
  policy_name: string
  params?: Record<string, unknown>
  asset_id: string
  side: string
  qty: number
  price: number
  nav?: number
  cash?: number
  positions?: Record<string, { qty?: number; avg_cost?: number; market_value?: number }>
  drawdown?: number
  as_of_date?: string
}

export interface RiskCheckResult {
  decision: 'approved' | 'clipped' | 'rejected'
  original_qty: number
  approved_qty: number
  reasons: string[]
}

export interface PositionRisk {
  asset_id: string
  weight: number
  market_value?: number
  beta?: number
  volatility?: number
  var_95?: number
}

export interface PortfolioRisk {
  positions: PositionRisk[]
  hhi: number
  max_weight: number
  sector_concentration: number
}

export interface RiskEvent {
  id: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  title: string
  description: string
  created_at: string
}

// ── API ────────────────────────────────────────────────────────────────────

export interface PortfolioVarResult {
  var: number
  cvar: number
  var_amount: number
  cvar_amount: number
  method: string
  confidence: number
}

export const riskApi = {
  policies: (config?: RequestConfig) =>
    api.get<PolicyInfo[]>('/risk/policies', config),

  sizers: (config?: RequestConfig) =>
    api.get<SizerInfo[]>('/risk/sizers', config),

  check: (body: RiskCheckRequest, config?: RequestConfig) =>
    api.post<RiskCheckResult>('/risk/check', body, config),

  getPositions: (config?: RequestConfig) =>
    api.get<PortfolioRisk>('/risk/positions', config),

  getEvents: (config?: RequestConfig) =>
    api.get<RiskEvent[]>('/risk/events', config),

  getPortfolioVar: (params: { method?: string; confidence?: number; horizon_days?: number; weights_json?: string; nav?: number }) =>
    api.get<PortfolioVarResult>(
      `/risk/portfolio-var?${new URLSearchParams(params as Record<string, string>)}`,
    ),
}

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

// ── API ────────────────────────────────────────────────────────────────────

export const riskApi = {
  policies: (config?: RequestConfig) =>
    api.get<PolicyInfo[]>('/risk/policies', config),

  sizers: (config?: RequestConfig) =>
    api.get<SizerInfo[]>('/risk/sizers', config),

  check: (body: RiskCheckRequest, config?: RequestConfig) =>
    api.post<RiskCheckResult>('/risk/check', body, config),
}

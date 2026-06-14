/**
 * cQuant API — Trading domain.
 */

import { api, type RequestConfig } from './client'

// ── Types (not yet in types/) ────────────────────────────────────────────────

export interface TradeOrder {
  order_id: string
  asset_id: string
  side: string
  qty: number
  order_type: string
  status: string
  filled_qty: number
  filled_price: number
  commission: number
  stamp_duty: number
  slippage: number
  total_cost: number
  reject_reason: string
  submitted_at: string | null
  filled_at: string | null
}

export interface TradePosition {
  asset_id: string
  qty: number
  avg_cost: number
  market_value: number
  unrealized_pnl: number
  realized_pnl: number
}

export interface TradeAccount {
  broker: string
  cash: number
  nav: number
  gross_exposure: number
  net_exposure: number
  realized_pnl: number
  unrealized_pnl: number
  positions_count: number
}

export interface TradePnL {
  broker: string
  nav: number
  realized_pnl: number
  unrealized_pnl: number
  total_pnl: number
  return_pct: number
}

// ── API ────────────────────────────────────────────────────────────────────

export const tradingApi = {
  account: (broker = 'paper', config?: RequestConfig) =>
    api.get<TradeAccount>(`/trading/account?broker=${broker}`, config),

  placeOrder: (
    body: {
      asset_id: string
      side: string
      qty: number
      order_type?: string
      limit_price?: number
      broker?: string
    },
    config?: RequestConfig,
  ) => api.post<TradeOrder>('/trading/order', body, config),

  cancelOrder: (orderId: string, broker = 'paper', config?: RequestConfig) =>
    api.delete<TradeOrder>(`/trading/order/${orderId}?broker=${broker}`, config),

  orders: (broker = 'paper', status?: string, config?: RequestConfig) => {
    const params = new URLSearchParams({ broker })
    if (status) params.set('status', status)
    return api.get<{ items: TradeOrder[]; total: number }>(
      `/trading/orders?${params}`,
      config,
    )
  },

  positions: (broker = 'paper', config?: RequestConfig) =>
    api.get<{ items: TradePosition[]; total: number }>(
      `/trading/positions?broker=${broker}`,
      config,
    ),

  fills: (broker = 'paper', config?: RequestConfig) =>
    api.get<{ items: TradeOrder[]; total: number }>(
      `/trading/fills?broker=${broker}`,
      config,
    ),

  pnl: (broker = 'paper', config?: RequestConfig) =>
    api.get<TradePnL>(`/trading/pnl?broker=${broker}`, config),
}

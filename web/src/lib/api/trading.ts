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

// ── Algo Order Types ───────────────────────────────────────────────────────

export interface AlgoOrderParams {
  asset_id: string
  side: 'buy' | 'sell'
  total_qty: number
  order_type: 'market' | 'limit' | 'twap' | 'vwap'
  limit_price?: number
  broker?: string
  start_time?: string   // ISO datetime — TWAP/VWAP
  end_time?: string     // ISO datetime — TWAP/VWAP
  num_slices?: number   // TWAP only
  lookback_days?: number // VWAP only
}

export interface AlgoSlice {
  slice_id: string
  scheduled_time: string
  status: 'pending' | 'filled' | 'cancelled' | 'failed'
  filled_price: number | null
  filled_qty: number | null
}

export interface AlgoOrderStatus {
  order_id: string
  asset_id: string
  side: string
  order_type: string
  total_qty: number
  status: 'active' | 'completed' | 'cancelled' | 'failed'
  slices: AlgoSlice[]
  filled_qty: number
  avg_price: number
  slippage: number
  created_at: string
  updated_at: string
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

  // ── Algo Orders ──────────────────────────────────────────────────────────

  placeAlgoOrder: (body: AlgoOrderParams, config?: RequestConfig) =>
    api.post<{ order_id: string; slices: AlgoSlice[] }>(
      '/trading/algo-order',
      body,
      config,
    ),

  getAlgoOrder: (orderId: string, config?: RequestConfig) =>
    api.get<AlgoOrderStatus>(`/trading/algo-order/${orderId}`, config),

  listAlgoOrders: (config?: RequestConfig) =>
    api.get<{ items: AlgoOrderStatus[] }>('/trading/algo-orders', config),

  cancelAlgoOrder: (orderId: string, config?: RequestConfig) =>
    api.delete(`/trading/algo-order/${orderId}`, config),
}

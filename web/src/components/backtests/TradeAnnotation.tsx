/**
 * TradeAnnotation — Convert backtest fills to KlineChart annotation markers.
 *
 * Provides utility functions for:
 *   - fillsToAnnotations: converts BacktestFill[] to TradeAnnotation[] with P&L
 *   - getAssetsFromFills: extracts unique asset IDs from fills
 */

import type { BacktestFill } from '@/lib/api/backtests'
import type { TradeAnnotation } from '@/components/charts/KlineChart'

/**
 * Convert backtest fills to KlineChart annotation markers.
 * Groups by asset, computes P&L for sell fills.
 */
export function fillsToAnnotations(fills: BacktestFill[]): TradeAnnotation[] {
  // Sort fills chronologically to ensure correct P&L tracking
  const sorted = [...fills].sort((a, b) => {
    const d = a.trade_date.localeCompare(b.trade_date)
    return d !== 0 ? d : (a.order_idx ?? 0) - (b.order_idx ?? 0)
  })

  // Track positions per asset for P&L computation
  const positions = new Map<string, { qty: number; avgCost: number }>()

  return sorted.map(fill => {
    const isBuy = fill.side === 'buy'

    // Update position tracking
    const pos = positions.get(fill.asset_id) || { qty: 0, avgCost: 0 }
    let pnl: number | undefined

    if (isBuy) {
      const totalCost = pos.avgCost * pos.qty + fill.price * fill.qty
      pos.qty += fill.qty
      pos.avgCost = pos.qty > 0 ? totalCost / pos.qty : 0
    } else {
      // Sell: compute P&L
      pnl = (fill.price - pos.avgCost) * fill.qty
      pos.qty -= fill.qty
      if (pos.qty <= 0) {
        pos.qty = 0
        pos.avgCost = 0
      }
    }
    positions.set(fill.asset_id, pos)

    // Build tooltip text
    const pnlText = pnl !== undefined ? ` P&L: ${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}` : ''
    const text = `${isBuy ? '买' : '卖'} ${fill.qty}股 @${fill.price.toFixed(2)}${pnlText}`

    return {
      time: fill.trade_date,
      position: isBuy ? 'belowBar' : 'aboveBar',
      color: isBuy ? '#22c55e' : '#ef4444',
      shape: isBuy ? 'arrowUp' : 'arrowDown',
      text,
    }
  })
}

/**
 * Get unique asset IDs from fills.
 */
export function getAssetsFromFills(fills: BacktestFill[]): string[] {
  return [...new Set(fills.map(f => f.asset_id))].sort()
}

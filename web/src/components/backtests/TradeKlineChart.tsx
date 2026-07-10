/**
 * TradeKlineChart — Container component for viewing trades on K-line charts.
 *
 * Features:
 *   - Asset selector (dropdown from fills data)
 *   - Period toggle (daily / weekly / monthly)
 *   - KlineChart with trade annotations overlaid
 */

import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { marketApi } from '@/lib/api/market'
import { backtestsApi } from '@/lib/api/backtests'
import { KlineChart } from '@/components/charts/KlineChart'
import { fillsToAnnotations, getAssetsFromFills } from './TradeAnnotation'
import { DataState } from '@/components/ui/DataState'

interface TradeKlineChartProps {
  backtestId: string
  height?: number
}

export function TradeKlineChart({ backtestId, height = 400 }: TradeKlineChartProps) {
  const [selectedAsset, setSelectedAsset] = useState('')
  const [period, setPeriod] = useState<'daily' | 'weekly' | 'monthly'>('daily')

  // Fetch all fills to get asset list
  const { data: fillsData } = useQuery({
    queryKey: ['backtest-fills-all', backtestId],
    queryFn: () => backtestsApi.getFills(backtestId, 0, 10000),
    staleTime: 60_000,
  })

  const assets = useMemo(() => {
    if (!fillsData?.items) return []
    return getAssetsFromFills(fillsData.items)
  }, [fillsData])

  // Auto-select first asset
  const effectiveAsset = selectedAsset || assets[0] || ''

  // Filter fills for selected asset
  const assetFills = useMemo(() => {
    if (!fillsData?.items || !effectiveAsset) return []
    return fillsData.items.filter(f => f.asset_id === effectiveAsset)
  }, [fillsData, effectiveAsset])

  // Get date range from fills
  const dateRange = useMemo(() => {
    if (assetFills.length === 0) return null
    const dates = assetFills.map(f => f.trade_date).sort()
    // Extend range by 3 months on each side for context
    const start = new Date(dates[0])
    const end = new Date(dates[dates.length - 1])
    start.setMonth(start.getMonth() - 3)
    end.setMonth(end.getMonth() + 3)
    return {
      start: start.toISOString().split('T')[0],
      end: end.toISOString().split('T')[0],
    }
  }, [assetFills])

  // Fetch OHLCV data
  const { data: priceData, isLoading } = useQuery({
    queryKey: ['market-prices', effectiveAsset, dateRange?.start, dateRange?.end, period],
    queryFn: () => marketApi.getPrices(effectiveAsset, dateRange!.start, dateRange!.end, period),
    enabled: !!effectiveAsset && !!dateRange,
    staleTime: 60_000,
  })

  // Convert fills to annotations
  const annotations = useMemo(() => {
    return fillsToAnnotations(assetFills)
  }, [assetFills])

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex items-end gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">资产</label>
          <select
            value={effectiveAsset}
            onChange={e => setSelectedAsset(e.target.value)}
            className="input-field text-sm w-48"
          >
            {assets.length === 0 && <option value="">无成交记录</option>}
            {assets.map(a => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">周期</label>
          <div className="flex gap-1">
            {(['daily', 'weekly', 'monthly'] as const).map(p => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1 text-sm rounded ${
                  period === p
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {p === 'daily' ? '日' : p === 'weekly' ? '周' : '月'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Chart */}
      {!effectiveAsset && (
        <div className="card flex items-center justify-center h-64 text-gray-400 text-sm">
          无成交记录
        </div>
      )}

      {effectiveAsset && (
        <DataState isLoading={isLoading} isEmpty={!priceData?.prices.length}>
          {priceData && priceData.prices.length > 0 && (
            <KlineChart
              data={priceData.prices}
              annotations={annotations}
              height={height}
              defaultRangeMonths={12}
            />
          )}
        </DataState>
      )}
    </div>
  )
}

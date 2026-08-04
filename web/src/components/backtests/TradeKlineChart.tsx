/**
 * TradeKlineChart — Container component for viewing trades on K-line charts.
 *
 * Features:
 *   - Asset selector (dropdown from fills data)
 *   - Period toggle (daily / weekly / monthly)
 *   - Days selector (time range filter)
 *   - KlineChart with trade annotations overlaid
 */

import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
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

const DAY_OPTIONS = [
  { value: 0, labelKey: 'page.market.all' },
  { value: 30, labelKey: 'page.market.last_30_days' },
  { value: 60, labelKey: 'page.market.last_60_days' },
  { value: 90, labelKey: 'page.market.last_90_days' },
  { value: 180, labelKey: 'page.market.last_180_days' },
  { value: 365, labelKey: 'page.market.last_1_year' },
] as const

export function TradeKlineChart({ backtestId, height = 400 }: TradeKlineChartProps) {
  const { t } = useTranslation()
  const [selectedAsset, setSelectedAsset] = useState('')
  const [period, setPeriod] = useState<'daily' | 'weekly' | 'monthly'>('daily')
  const [days, setDays] = useState<number>(0) // 0 = all

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

  // Filter prices by days parameter
  const filteredPrices = useMemo(() => {
    if (!priceData?.prices || days === 0) return priceData?.prices || []
    const now = new Date()
    const cutoffDate = new Date(now.getTime() - days * 24 * 60 * 60 * 1000)
    return priceData.prices.filter(p => new Date(p.trade_date) >= cutoffDate)
  }, [priceData, days])

  // Convert fills to annotations
  const annotations = useMemo(() => {
    return fillsToAnnotations(assetFills)
  }, [assetFills])

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex items-end gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t('page.market.asset')}</label>
          <select
            value={effectiveAsset}
            onChange={e => setSelectedAsset(e.target.value)}
            className="input-field text-sm w-48"
          >
            {assets.length === 0 && <option value="">{t('common.no_data')}</option>}
            {assets.map(a => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t('page.market.period')}</label>
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
                {t(`page.market.${p}`)}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t('page.market.days')}</label>
          <select
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            className="input-field text-sm w-32"
          >
            {DAY_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>
                {t(opt.labelKey)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Chart */}
      {!effectiveAsset && (
        <div className="card flex items-center justify-center h-64 text-gray-400 text-sm">
          {t('common.no_data')}
        </div>
      )}

      {effectiveAsset && (
        <DataState isLoading={isLoading} isEmpty={filteredPrices.length === 0}>
          {filteredPrices.length > 0 && (
            <KlineChart
              data={filteredPrices}
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

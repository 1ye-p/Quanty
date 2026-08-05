import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { marketApi } from '@/lib/api/market'
import { KlineChart } from '@/components/charts/KlineChart'
import { PriceStats } from './PriceStats'
import { AssetSearch } from './AssetSearch'
import { DataState } from '@/components/ui/DataState'

export function PriceChart() {
  const { t } = useTranslation()
  const [assetId, setAssetId] = useState('')
  const [dateRange, setDateRange] = useState(() => {
    const end = new Date()
    const start = new Date()
    start.setMonth(start.getMonth() - 8)
    return {
      start: start.toISOString().split('T')[0],
      end: end.toISOString().split('T')[0],
    }
  })

  const { data, isLoading, error } = useQuery({
    queryKey: ['market-prices', assetId, dateRange.start, dateRange.end],
    queryFn: () => marketApi.getPrices(assetId, dateRange.start, dateRange.end),
    enabled: !!assetId,
    staleTime: 60_000,
  })

  return (
    <div className="space-y-4">
      {/* Search and controls */}
      <div className="flex items-end gap-3">
        <div className="flex-1">
          <label className="block text-xs text-gray-500 mb-1">{t('component.datasets.price_chart.asset_label')}</label>
          <AssetSearch value={assetId} onChange={setAssetId} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t('common.start_date')}</label>
          <input
            type="date"
            value={dateRange.start}
            onChange={e => setDateRange(r => ({ ...r, start: e.target.value }))}
            className="input-field text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t('common.end_date')}</label>
          <input
            type="date"
            value={dateRange.end}
            onChange={e => setDateRange(r => ({ ...r, end: e.target.value }))}
            className="input-field text-sm"
          />
        </div>
      </div>

      {/* Content */}
      {!assetId && (
        <div className="card flex items-center justify-center h-64 text-gray-400 text-sm">
          {t('component.datasets.price_chart.prompt_asset')}
        </div>
      )}

      {assetId && (
        <DataState isLoading={isLoading} error={error} isEmpty={data && data.prices.length === 0} emptyText={t('component.datasets.price_chart.empty_no_data')}>
          {data && data.prices.length > 0 && (
            <>
              <PriceStats stats={data.stats} />
              <KlineChart data={data.prices} height={400} defaultRangeMonths={8} />
            </>
          )}
        </DataState>
      )}
    </div>
  )
}

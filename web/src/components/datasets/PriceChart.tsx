import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { marketApi } from '@/lib/api/market'
import { KlineChart } from '@/components/charts/KlineChart'
import { PriceStats } from './PriceStats'
import { AssetSearch } from './AssetSearch'
import { DataState } from '@/components/ui/DataState'

export function PriceChart() {
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
          <label className="block text-xs text-gray-500 mb-1">股票代码</label>
          <AssetSearch value={assetId} onChange={setAssetId} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">起始日期</label>
          <input
            type="date"
            value={dateRange.start}
            onChange={e => setDateRange(r => ({ ...r, start: e.target.value }))}
            className="input-field text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">结束日期</label>
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
          请输入股票代码查看行情
        </div>
      )}

      {assetId && (
        <DataState isLoading={isLoading} error={error} isEmpty={data && data.prices.length === 0} emptyText="该时间段无数据">
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

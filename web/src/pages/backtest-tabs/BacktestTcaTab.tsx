import { MetricCard } from '../../components/ui/MetricCard'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { backtestsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'


export function BacktestTcaTab() {
  const { id: selectedId } = useParams<{ id: string }>()

  const { data: tcaData } = useQuery({
    queryKey: queryKeys.backtests.tca(selectedId!),
    queryFn: () => backtestsApi.getTca(selectedId!),
    enabled: !!selectedId,
  })

  if (!selectedId) return null

  return (
    <div className="space-y-4">
      {tcaData ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <MetricCard label="Total Cost" value={`${Number(tcaData.total_cost ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`} />
            <MetricCard label="Cost Ratio" value={`${Number(tcaData.cost_pct_turnover ?? 0).toFixed(4)}%`} />
            <MetricCard label="Trade Count" value={String(tcaData.num_trades ?? 0)} />
            <MetricCard label="Avg Cost/Trade" value={`${Number(tcaData.cost_per_trade ?? 0).toFixed(2)}`} />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="card p-4">
              <div className="text-xs text-gray-500 mb-1">Commission</div>
              <div className="text-lg font-semibold">{Number(tcaData.total_commission ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-gray-500 mb-1">Stamp Duty</div>
              <div className="text-lg font-semibold">{Number(tcaData.total_stamp_duty ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</div>
            </div>
            <div className="card p-4">
              <div className="text-xs text-gray-500 mb-1">Slippage</div>
              <div className="text-lg font-semibold">{Number(tcaData.total_slippage ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</div>
            </div>
          </div>
        </>
      ) : (
        <div className="text-center text-gray-400 py-12">No trade data available for cost analysis</div>
      )}
    </div>
  )
}

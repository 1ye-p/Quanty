import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { backtestsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

function MetricCard({ label, value, sub, warn = false }: {
  label: string; value: string | number; sub?: string; warn?: boolean
}) {
  return (
    <div className={`card text-center py-4 ${warn ? 'border-l-4 border-red-400' : ''}`}>
      <div className={`text-xl font-bold ${warn ? 'text-red-600' : 'text-brand-600'}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  )
}

export function BacktestAttributionTab() {
  const { id: selectedId } = useParams<{ id: string }>()

  const { data: attributionData } = useQuery({
    queryKey: queryKeys.backtests.attribution(selectedId!),
    queryFn: () => backtestsApi.getAttribution(selectedId!),
    enabled: !!selectedId,
  })

  if (!selectedId) return null

  return (
    <div className="space-y-4">
      {attributionData ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <MetricCard label="Active Return" value={`${Number(attributionData.active_return ?? 0 * 100).toFixed(2)}%`} warn={Number(attributionData.active_return ?? 0) < 0} />
            <MetricCard label="Allocation Effect" value={`${(Number(attributionData.allocation_effect ?? 0) * 100).toFixed(2)}%`} />
            <MetricCard label="Selection Effect" value={`${(Number(attributionData.selection_effect ?? 0) * 100).toFixed(2)}%`} />
            <MetricCard label="Interaction Effect" value={`${(Number(attributionData.interaction_effect ?? 0) * 100).toFixed(2)}%`} />
          </div>
          {Object.keys(attributionData.sector_details as Record<string, unknown> ?? {}).length > 0 && (
            <div className="card p-4">
              <div className="text-sm font-medium text-gray-700 mb-3">Sector Attribution Detail</div>
              <table className="w-full text-xs">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="table-th">Sector</th>
                    <th className="table-th">Portfolio Weight</th>
                    <th className="table-th">Benchmark Weight</th>
                    <th className="table-th">Portfolio Return</th>
                    <th className="table-th">Benchmark Return</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(attributionData.sector_details as Record<string, Record<string, number>>).map(([sector, data]) => (
                    <tr key={sector} className="table-row">
                      <td className="table-td">{sector}</td>
                      <td className="table-td">{((data.port_weight ?? 0) * 100).toFixed(1)}%</td>
                      <td className="table-td">{((data.bench_weight ?? 0) * 100).toFixed(1)}%</td>
                      <td className="table-td">{((data.port_return ?? 0) * 100).toFixed(2)}%</td>
                      <td className="table-td">{((data.bench_return ?? 0) * 100).toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : (
        <div className="text-center text-gray-400 py-12">No benchmark set or single-asset portfolio; attribution analysis unavailable</div>
      )}
    </div>
  )
}

import { MetricCard } from '../../components/ui/MetricCard'
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { backtestsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { AttributionBreakdown, type AttributionEntry } from '@/components/charts/AttributionBreakdown'


export function BacktestAttributionTab() {
  const { id: selectedId } = useParams<{ id: string }>()

  const { data: attributionData } = useQuery({
    queryKey: queryKeys.backtests.attribution(selectedId!),
    queryFn: () => backtestsApi.getAttribution(selectedId!),
    enabled: !!selectedId,
  })

  // Transform sector_details into AttributionEntry format
  const attributionEntries = useMemo((): AttributionEntry[] => {
    if (!attributionData?.sector_details) return []

    const sectorDetails = attributionData.sector_details as Record<string, Record<string, number>>
    const entries: AttributionEntry[] = []

    for (const [sector, data] of Object.entries(sectorDetails)) {
      // Compute sector-level effects from weights and returns
      const portWeight = data.port_weight ?? 0
      const benchWeight = data.bench_weight ?? 0
      const portReturn = data.port_return ?? 0
      const benchReturn = data.bench_return ?? 0

      // Brinson attribution effects at sector level
      // Allocation: (wp - wb) * (rb - Rb) - we approximate using sector returns
      const allocationEffect = (portWeight - benchWeight) * benchReturn
      // Selection: wb * (rp - rb)
      const selectionEffect = benchWeight * (portReturn - benchReturn)
      // Interaction: (wp - wb) * (rp - rb)
      const interactionEffect = (portWeight - benchWeight) * (portReturn - benchReturn)

      entries.push({
        name: sector,
        allocation_effect: allocationEffect,
        selection_effect: selectionEffect,
        interaction_effect: interactionEffect,
      })
    }

    // Sort by absolute total effect descending
    return entries.sort((a, b) => {
      const totalA = Math.abs(a.allocation_effect + a.selection_effect + a.interaction_effect)
      const totalB = Math.abs(b.allocation_effect + b.selection_effect + b.interaction_effect)
      return totalB - totalA
    })
  }, [attributionData])

  if (!selectedId) return null

  return (
    <div className="space-y-4">
      {attributionData ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <MetricCard label="Active Return" value={`${(Number(attributionData.active_return ?? 0) * 100).toFixed(2)}%`} warn={Number(attributionData.active_return ?? 0) < 0} />
            <MetricCard label="Allocation Effect" value={`${(Number(attributionData.allocation_effect ?? 0) * 100).toFixed(2)}%`} />
            <MetricCard label="Selection Effect" value={`${(Number(attributionData.selection_effect ?? 0) * 100).toFixed(2)}%`} />
            <MetricCard label="Interaction Effect" value={`${(Number(attributionData.interaction_effect ?? 0) * 100).toFixed(2)}%`} />
          </div>

          {/* Attribution Breakdown Chart */}
          {attributionEntries.length > 0 && (
            <AttributionBreakdown data={attributionEntries} stacked={true} />
          )}

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

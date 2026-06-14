/**
 * ICTimeseriesHeatmap — IC time series heatmap across factors and time periods.
 *
 * HTML table with color coding: blue for positive IC, red for negative.
 * Granularity selector: week/month/quarter.
 * Shows last 20 periods, top 20 factors.
 */
import { useState, useMemo } from 'react'

export interface ICDataPoint {
  period: string     // e.g. "2025-W01", "2025-01", "2025-Q1"
  factor: string
  ic: number         // Information Coefficient (-1 to 1)
}

interface Props {
  data: ICDataPoint[]
  title?: string
}

type Granularity = 'week' | 'month' | 'quarter'

const GRANULARITY_OPTIONS: { key: Granularity; label: string }[] = [
  { key: 'week', label: 'Weekly' },
  { key: 'month', label: 'Monthly' },
  { key: 'quarter', label: 'Quarterly' },
]

const MAX_PERIODS = 20
const MAX_FACTORS = 20

function icColor(ic: number): { bg: string; text: string } {
  const abs = Math.abs(ic)
  if (ic > 0) {
    if (abs > 0.08) return { bg: 'bg-blue-700', text: 'text-white' }
    if (abs > 0.05) return { bg: 'bg-blue-500', text: 'text-white' }
    if (abs > 0.03) return { bg: 'bg-blue-300', text: 'text-blue-900' }
    return { bg: 'bg-blue-100', text: 'text-blue-800' }
  }
  if (ic < 0) {
    if (abs > 0.08) return { bg: 'bg-red-700', text: 'text-white' }
    if (abs > 0.05) return { bg: 'bg-red-500', text: 'text-white' }
    if (abs > 0.03) return { bg: 'bg-red-300', text: 'text-red-900' }
    return { bg: 'bg-red-100', text: 'text-red-800' }
  }
  return { bg: 'bg-gray-50', text: 'text-gray-400' }
}

function filterByGranularity(data: ICDataPoint[], _gran: Granularity): ICDataPoint[] {
  // The period string already encodes the granularity (W/week, YYYY-MM/month, Q/quarter).
  // In practice the upstream data source should provide pre-aggregated data per granularity.
  // Here we just pass through; filtering by prefix could be added if needed.
  return data
}

export function ICTimeseriesHeatmap({ data, title = 'IC Timeseries Heatmap' }: Props) {
  const [granularity, setGranularity] = useState<Granularity>('month')

  const { periods, factors, matrix } = useMemo(() => {
    const filtered = filterByGranularity(data, granularity)
    if (filtered.length === 0) return { periods: [], factors: [], matrix: new Map<string, number>() }

    // Unique periods (sorted descending to show latest first)
    const periodSet = new Set(filtered.map(d => d.period))
    const allPeriods = Array.from(periodSet).sort().reverse().slice(0, MAX_PERIODS)
    const periods = allPeriods.reverse() // chronological order for display

    // Rank factors by average absolute IC, take top N
    const factorIcMap = new Map<string, number[]>()
    for (const d of filtered) {
      const arr = factorIcMap.get(d.factor) ?? []
      arr.push(d.ic)
      factorIcMap.set(d.factor, arr)
    }
    const factorRanking = Array.from(factorIcMap.entries())
      .map(([name, ics]) => ({
        name,
        avgAbsIc: ics.reduce((s, v) => s + Math.abs(v), 0) / ics.length,
      }))
      .sort((a, b) => b.avgAbsIc - a.avgAbsIc)
      .slice(0, MAX_FACTORS)
      .map(f => f.name)

    // Build lookup matrix
    const matrix = new Map<string, number>()
    for (const d of filtered) {
      if (factorRanking.includes(d.factor) && periods.includes(d.period)) {
        matrix.set(`${d.factor}::${d.period}`, d.ic)
      }
    }

    return { periods, factors: factorRanking, matrix }
  }, [data, granularity])

  if (!data || data.length === 0) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-2">{title}</h3>
        <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
          No IC data available
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800">{title}</h3>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-0.5">
          {GRANULARITY_OPTIONS.map(g => (
            <button
              key={g.key}
              onClick={() => setGranularity(g.key)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                granularity === g.key
                  ? 'bg-white text-gray-800 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {g.label}
            </button>
          ))}
        </div>
      </div>

      {factors.length === 0 || periods.length === 0 ? (
        <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
          No matching data for selected granularity
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="text-gray-500">
                <th className="py-1.5 px-2 text-left font-medium sticky left-0 bg-white z-10 min-w-[100px]">
                  Factor
                </th>
                {periods.map(p => (
                  <th key={p} className="py-1.5 px-1 text-center font-medium min-w-[56px] whitespace-nowrap">
                    {p}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {factors.map(factor => (
                <tr key={factor} className="hover:bg-gray-50/50">
                  <td className="py-1 px-2 font-medium text-gray-700 sticky left-0 bg-white z-10 truncate max-w-[120px]"
                    title={factor}
                  >
                    {factor}
                  </td>
                  {periods.map(period => {
                    const ic = matrix.get(`${factor}::${period}`)
                    const color = ic != null ? icColor(ic) : { bg: 'bg-gray-50', text: 'text-gray-300' }
                    return (
                      <td key={period} className="py-0.5 px-0.5">
                        <div
                          className={`rounded py-1 px-0.5 text-center font-medium ${color.bg} ${color.text}`}
                          title={ic != null ? `${factor}: ${ic.toFixed(4)}` : `${factor}: -`}
                        >
                          {ic != null ? ic.toFixed(3) : '-'}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center justify-center gap-3 mt-4 flex-wrap">
        <span className="text-xs text-gray-500 mr-1">IC:</span>
        {[
          { label: '>0.08', bg: 'bg-blue-700', text: 'text-white' },
          { label: '0.05-0.08', bg: 'bg-blue-500', text: 'text-white' },
          { label: '0.03-0.05', bg: 'bg-blue-300', text: 'text-blue-900' },
          { label: '<0.03', bg: 'bg-blue-100', text: 'text-blue-800' },
          { label: '0', bg: 'bg-gray-50', text: 'text-gray-400' },
          { label: '>-0.03', bg: 'bg-red-100', text: 'text-red-800' },
          { label: '-0.03~-0.05', bg: 'bg-red-300', text: 'text-red-900' },
          { label: '-0.05~-0.08', bg: 'bg-red-500', text: 'text-white' },
          { label: '<-0.08', bg: 'bg-red-700', text: 'text-white' },
        ].map(item => (
          <div key={item.label} className="flex items-center gap-1">
            <div className={`w-4 h-3 rounded-sm ${item.bg}`} />
            <span className="text-xs text-gray-500">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

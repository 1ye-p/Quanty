import { useMemo } from 'react'

interface SensitivityHeatmapProps {
  data: Record<string, any>[]
  paramX: string
  paramY: string
  metricKey: string
  height?: number
}

export function SensitivityHeatmap({ data, paramX, paramY, metricKey }: SensitivityHeatmapProps) {
  // Build grid from data
  const { xValues, yValues, grid, minVal, maxVal } = useMemo(() => {
    if (!data || data.length === 0) return { xValues: [], yValues: [], grid: {}, minVal: 0, maxVal: 1 }

    const numSort = (a: unknown, b: unknown) => {
      const na = Number(a), nb = Number(b)
      return !isNaN(na) && !isNaN(nb) ? na - nb : String(a).localeCompare(String(b))
    }
    const xs = [...new Set(data.map(d => d[paramX]))].sort(numSort)
    const ys = [...new Set(data.map(d => d[paramY]))].sort(numSort)

    const gridMap: Record<string, Record<string, number>> = {}
    let min = Infinity
    let max = -Infinity

    for (const d of data) {
      const x = d[paramX]
      const y = d[paramY]
      const val = d[metricKey] ?? 0
      if (!gridMap[y]) gridMap[y] = {}
      gridMap[y][x] = val
      min = Math.min(min, val)
      max = Math.max(max, val)
    }

    return { xValues: xs, yValues: ys, grid: gridMap, minVal: min, maxVal: max }
  }, [data, paramX, paramY, metricKey])

  const getColor = (value: number) => {
    if (maxVal === minVal) return 'bg-gray-100'
    const ratio = (value - minVal) / (maxVal - minVal)
    if (ratio < 0.2) return 'bg-red-100'
    if (ratio < 0.4) return 'bg-orange-100'
    if (ratio < 0.6) return 'bg-yellow-100'
    if (ratio < 0.8) return 'bg-green-100'
    return 'bg-blue-100'
  }

  if (xValues.length === 0 || yValues.length === 0) {
    return (
      <div className="card flex items-center justify-center h-48 text-gray-400 text-sm">
        需要 2D 参数网格数据
      </div>
    )
  }

  return (
    <div className="card p-4">
      <h4 className="text-sm font-medium text-gray-700 mb-3">参数热力图 ({metricKey})</h4>
      <div className="overflow-x-auto">
        <table className="text-xs">
          <thead>
            <tr>
              <th className="px-2 py-1 text-gray-500">{paramY} ↓ / {paramX} →</th>
              {xValues.map(x => (
                <th key={String(x)} className="px-3 py-1 text-gray-600 font-medium">{String(x)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {yValues.map(y => (
              <tr key={String(y)}>
                <td className="px-2 py-1 text-gray-600 font-medium">{String(y)}</td>
                {xValues.map(x => {
                  const val = grid[y]?.[x]
                  return (
                    <td
                      key={String(x)}
                      className={`px-3 py-2 text-center ${val !== undefined ? getColor(val) : 'bg-gray-50'}`}
                      title={`${paramX}=${x}, ${paramY}=${y}: ${val?.toFixed(4) ?? '-'}`}
                    >
                      {val !== undefined ? val.toFixed(3) : '-'}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-2 mt-2 text-[10px] text-gray-400">
        <span>低</span>
        <div className="flex gap-0.5">
          {['bg-red-100', 'bg-orange-100', 'bg-yellow-100', 'bg-green-100', 'bg-blue-100'].map(c => (
            <div key={c} className={`w-4 h-2 ${c}`} />
          ))}
        </div>
        <span>高</span>
      </div>
    </div>
  )
}

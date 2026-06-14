/**
 * Monthly returns heatmap component.
 * Displays a grid of monthly returns with color-coded cells.
 */

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

interface MonthlyReturn {
  year: number
  month: number
  return: number
}

function heatmapColor(val: number): string {
  if (val > 0) {
    const intensity = Math.min(Math.abs(val) * 5, 0.8)
    return `rgba(34, 197, 94, ${intensity})`
  }
  if (val < 0) {
    const intensity = Math.min(Math.abs(val) * 5, 0.8)
    return `rgba(239, 68, 68, ${intensity})`
  }
  return '#f3f4f6'
}

export function MonthlyHeatmap({ data }: { data: MonthlyReturn[] }) {
  if (!data || data.length === 0) return null

  const years = [...new Set(data.map(d => d.year))].sort()
  const lookup = new Map(data.map(d => [`${d.year}-${d.month}`, d.return]))

  return (
    <div className="card">
      <h3 className="font-semibold text-gray-800 mb-3">Monthly Returns</h3>
      <div className="overflow-x-auto">
        <table className="text-xs w-full">
          <thead>
            <tr>
              <th className="px-2 py-1 text-left text-gray-500">Year</th>
              {MONTHS.map(m => (
                <th key={m} className="px-2 py-1 text-center text-gray-500">{m}</th>
              ))}
              <th className="px-2 py-1 text-center text-gray-500 font-medium">Annual</th>
            </tr>
          </thead>
          <tbody>
            {years.map(year => {
              let annualReturn = 1
              for (let m = 1; m <= 12; m++) {
                const r = lookup.get(`${year}-${m}`)
                if (r !== undefined) annualReturn *= (1 + r)
              }
              annualReturn -= 1
              return (
                <tr key={year}>
                  <td className="px-2 py-1 font-medium text-gray-700">{year}</td>
                  {Array.from({ length: 12 }, (_, i) => i + 1).map(month => {
                    const val = lookup.get(`${year}-${month}`)
                    return (
                      <td
                        key={month}
                        className="px-2 py-1 text-center font-mono"
                        style={{
                          backgroundColor: val !== undefined ? heatmapColor(val) : '#f9fafb',
                          color: val !== undefined && Math.abs(val) > 0.15 ? 'white' : '#374151',
                        }}
                      >
                        {val !== undefined ? `${(val * 100).toFixed(1)}%` : '—'}
                      </td>
                    )
                  })}
                  <td
                    className="px-2 py-1 text-center font-mono font-medium"
                    style={{
                      backgroundColor: heatmapColor(annualReturn),
                      color: Math.abs(annualReturn) > 0.15 ? 'white' : '#374151',
                    }}
                  >
                    {(annualReturn * 100).toFixed(1)}%
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

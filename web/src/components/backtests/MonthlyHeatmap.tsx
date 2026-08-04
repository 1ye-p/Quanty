/**
 * Monthly returns heatmap component.
 * Displays a grid of monthly returns with color-coded cells.
 */
import { useTranslation } from 'react-i18next'

const MONTH_KEYS = [
  'component.backtests.monthly_heatmap.month_jan',
  'component.backtests.monthly_heatmap.month_feb',
  'component.backtests.monthly_heatmap.month_mar',
  'component.backtests.monthly_heatmap.month_apr',
  'component.backtests.monthly_heatmap.month_may',
  'component.backtests.monthly_heatmap.month_jun',
  'component.backtests.monthly_heatmap.month_jul',
  'component.backtests.monthly_heatmap.month_aug',
  'component.backtests.monthly_heatmap.month_sep',
  'component.backtests.monthly_heatmap.month_oct',
  'component.backtests.monthly_heatmap.month_nov',
  'component.backtests.monthly_heatmap.month_dec',
]

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
  const { t } = useTranslation()
  if (!data || data.length === 0) return null

  const years = [...new Set(data.map(d => d.year))].sort()
  const lookup = new Map(data.map(d => [`${d.year}-${d.month}`, d.return]))

  return (
    <div className="card">
      <h3 className="font-semibold text-gray-800 mb-3">{t('component.backtests.monthly_heatmap.title')}</h3>
      <div className="overflow-x-auto">
        <table className="text-xs w-full">
          <thead>
            <tr>
              <th className="px-2 py-1 text-left text-gray-500">{t('component.backtests.monthly_heatmap.year')}</th>
              {MONTH_KEYS.map(mk => (
                <th key={mk} className="px-2 py-1 text-center text-gray-500">{t(mk)}</th>
              ))}
              <th className="px-2 py-1 text-center text-gray-500 font-medium">{t('component.backtests.monthly_heatmap.annual')}</th>
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

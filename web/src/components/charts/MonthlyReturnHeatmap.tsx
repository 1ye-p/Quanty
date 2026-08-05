/**
 * MonthlyReturnHeatmap — Color-coded monthly returns table with year totals.
 *
 * Color thresholds:
 *   >5%   dark green  (bg-green-700)
 *   >2%   green       (bg-green-500)
 *   >0%   light green (bg-green-200)
 *   >=-2%  light red   (bg-red-200)
 *   >=-5%  red         (bg-red-500)
 *   <-5%  dark red    (bg-red-700)
 */
import { useTranslation } from 'react-i18next'

export interface MonthlyReturnRow {
  year: number
  /** 12 monthly returns as fractions (0.05 = 5%). Null/undefined = no data. */
  months: (number | null | undefined)[]
}

interface Props {
  data: MonthlyReturnRow[]
  title?: string
}

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function cellColor(value: number | null | undefined): string {
  if (value == null || !isFinite(value)) return 'bg-gray-50 text-gray-300'
  const pct = value * 100
  if (pct > 5) return 'bg-green-700 text-white'
  if (pct > 2) return 'bg-green-500 text-white'
  if (pct > 0) return 'bg-green-200 text-green-900'
  if (pct >= -2) return 'bg-red-200 text-red-900'
  if (pct >= -5) return 'bg-red-500 text-white'
  return 'bg-red-700 text-white'
}

function yearTotal(months: (number | null | undefined)[]): number | null {
  const valid = months.filter((m): m is number => m != null && isFinite(m))
  if (valid.length === 0) return null
  // Compound returns
  return valid.reduce((acc, r) => acc * (1 + r), 1) - 1
}

const LEGEND_ITEMS = [
  { label: '>5%', className: 'bg-green-700' },
  { label: '2-5%', className: 'bg-green-500' },
  { label: '0-2%', className: 'bg-green-200' },
  { label: '0 to -2%', className: 'bg-red-200' },
  { label: '-2 to -5%', className: 'bg-red-500' },
  { label: '<-5%', className: 'bg-red-700' },
]

export function MonthlyReturnHeatmap({ data, title }: Props) {
  const { t } = useTranslation()
  const resolvedTitle = title ?? t('component.charts.monthly_return_heatmap.title')
  if (!data || data.length === 0) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-2">{resolvedTitle}</h3>
        <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
          {t('component.charts.monthly_return_heatmap.no_data')}
        </div>
      </div>
    )
  }

  const sorted = [...data].sort((a, b) => b.year - a.year)

  return (
    <div className="card">
      <h3 className="font-semibold text-gray-800 mb-4">{resolvedTitle}</h3>

      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="text-gray-500">
              <th className="py-1.5 px-2 text-left font-medium sticky left-0 bg-white">{t('component.charts.monthly_return_heatmap.col_year')}</th>
              {MONTH_LABELS.map(m => (
                <th key={m} className="py-1.5 px-2 text-center font-medium">{m}</th>
              ))}
              <th className="py-1.5 px-2 text-center font-medium border-l border-gray-200">{t('component.charts.monthly_return_heatmap.col_total')}</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(row => {
              const total = yearTotal(row.months)
              return (
                <tr key={row.year} className="hover:bg-gray-50">
                  <td className="py-1 px-2 font-medium text-gray-700 sticky left-0 bg-white">{row.year}</td>
                  {row.months.map((val, i) => (
                    <td key={i} className="py-1 px-0.5">
                      <div
                        className={`rounded py-1 px-1 text-center font-medium ${cellColor(val)}`}
                        title={val != null && isFinite(val) ? `${(val * 100).toFixed(2)}%` : '-'}
                      >
                        {val != null && isFinite(val) ? `${(val * 100).toFixed(1)}%` : '-'}
                      </div>
                    </td>
                  ))}
                  <td className="py-1 px-0.5 border-l border-gray-200">
                    <div
                      className={`rounded py-1 px-1 text-center font-bold ${cellColor(total)}`}
                    >
                      {total != null && isFinite(total) ? `${(total * 100).toFixed(1)}%` : '-'}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-3 mt-4 flex-wrap">
        {LEGEND_ITEMS.map(item => (
          <div key={item.label} className="flex items-center gap-1">
            <div className={`w-4 h-3 rounded-sm ${item.className}`} />
            <span className="text-xs text-gray-500">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * FactorCorrelationMatrix — Factor correlation matrix heatmap.
 *
 * HTML table with color coding: blue for positive correlation, red for negative.
 * Intensity based on absolute value: >0.8 strong, >0.6 medium, >0.4 moderate, >0.2 weak.
 * Diagonal is always 1.0 (self-correlation).
 */
import { useTranslation } from 'react-i18next'

export interface CorrelationMatrixData {
  factors: string[]
  /** Flattened row-major matrix. matrix[i * n + j] = correlation(factors[i], factors[j]) */
  matrix: number[]
}

interface Props {
  data: CorrelationMatrixData
  title?: string
}

function corrColor(value: number): { bg: string; text: string } {
  // Diagonal (self-correlation) = special gold highlight
  if (value === 1.0) return { bg: 'bg-amber-100', text: 'text-amber-800 font-bold' }

  const abs = Math.abs(value)

  if (value > 0) {
    // Positive: blue spectrum
    if (abs > 0.8) return { bg: 'bg-blue-800', text: 'text-white' }
    if (abs > 0.6) return { bg: 'bg-blue-600', text: 'text-white' }
    if (abs > 0.4) return { bg: 'bg-blue-400', text: 'text-white' }
    if (abs > 0.2) return { bg: 'bg-blue-200', text: 'text-blue-900' }
    return { bg: 'bg-blue-50', text: 'text-blue-700' }
  }

  if (value < 0) {
    // Negative: red spectrum
    if (abs > 0.8) return { bg: 'bg-red-800', text: 'text-white' }
    if (abs > 0.6) return { bg: 'bg-red-600', text: 'text-white' }
    if (abs > 0.4) return { bg: 'bg-red-400', text: 'text-white' }
    if (abs > 0.2) return { bg: 'bg-red-200', text: 'text-red-900' }
    return { bg: 'bg-red-50', text: 'text-red-700' }
  }

  return { bg: 'bg-gray-50', text: 'text-gray-400' }
}

function getCorrelation(data: CorrelationMatrixData, i: number, j: number): number {
  const n = data.factors.length
  return data.matrix[i * n + j]
}

const LEGEND_ITEMS = [
  { label: '>0.8', bg: 'bg-blue-800', text: 'text-white' },
  { label: '0.6-0.8', bg: 'bg-blue-600', text: 'text-white' },
  { label: '0.4-0.6', bg: 'bg-blue-400', text: 'text-white' },
  { label: '0.2-0.4', bg: 'bg-blue-200', text: 'text-blue-900' },
  { label: '<0.2', bg: 'bg-blue-50', text: 'text-blue-700' },
  { label: '0', bg: 'bg-gray-50', text: 'text-gray-400' },
  { label: '>-0.2', bg: 'bg-red-50', text: 'text-red-700' },
  { label: '-0.2~-0.4', bg: 'bg-red-200', text: 'text-red-900' },
  { label: '-0.4~-0.6', bg: 'bg-red-400', text: 'text-white' },
  { label: '-0.6~-0.8', bg: 'bg-red-600', text: 'text-white' },
  { label: '<-0.8', bg: 'bg-red-800', text: 'text-white' },
]

export function FactorCorrelationMatrix({ data, title }: Props) {
  const { t } = useTranslation()
  const resolvedTitle = title ?? t('component.charts.factor_correlation_matrix.title')
  if (!data || !data.factors || data.factors.length === 0 || !data.matrix || data.matrix.length === 0) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-2">{resolvedTitle}</h3>
        <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
          {t('component.charts.factor_correlation_matrix.no_data')}
        </div>
      </div>
    )
  }

  const { factors } = data
  const n = factors.length

  // Validate matrix size
  if (data.matrix.length !== n * n) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-2">{resolvedTitle}</h3>
        <div className="flex items-center justify-center h-40 text-red-400 text-sm">
          {t('component.charts.factor_correlation_matrix.matrix_mismatch', { expected: n * n, actual: data.matrix.length })}
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <h3 className="font-semibold text-gray-800 mb-4">{resolvedTitle}</h3>

      <div className="overflow-x-auto">
        <table className="text-xs border-collapse">
          <thead>
            <tr>
              <th className="py-1 px-1 sticky left-0 bg-white z-10" />
              {factors.map((f, j) => (
                <th
                  key={j}
                  className="py-1 px-1 font-medium text-gray-500 text-center min-w-[52px] whitespace-nowrap"
                  style={{ writingMode: 'vertical-lr', transform: 'rotate(180deg)', height: '80px' }}
                  title={f}
                >
                  <span className="truncate block max-h-[70px] overflow-hidden">{f}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {factors.map((factor, i) => (
              <tr key={i} className="hover:bg-gray-50/30">
                <td
                  className="py-1 px-2 font-medium text-gray-700 text-right sticky left-0 bg-white z-10 whitespace-nowrap max-w-[120px] truncate"
                  title={factor}
                >
                  {factor}
                </td>
                {factors.map((_, j) => {
                  const val = getCorrelation(data, i, j)
                  const color = corrColor(val)
                  return (
                    <td key={j} className="p-0.5">
                      <div
                        className={`rounded py-1.5 px-1 text-center font-medium min-w-[48px] ${color.bg} ${color.text}`}
                        title={`${factors[i]} vs ${factors[j]}: ${val.toFixed(3)}`}
                      >
                        {val.toFixed(2)}
                      </div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-2 mt-4 flex-wrap">
        <span className="text-xs text-gray-500 mr-1">{t('component.charts.factor_correlation_matrix.legend_label')}</span>
        {LEGEND_ITEMS.map(item => (
          <div key={item.label} className="flex items-center gap-1">
            <div className={`w-3.5 h-2.5 rounded-sm ${item.bg}`} />
            <span className="text-xs text-gray-500">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * CollapsedMarkerTooltip — Tooltip for collapsed annotation markers on K-line chart.
 *
 * Displays:
 *   - Date
 *   - Total trade count
 *   - Buy/sell breakdown
 *   - Individual trades with asset, price, and P&L
 */

import { useTranslation } from 'react-i18next'
import type { CollapsedAnnotation } from './annotationUtils'

interface CollapsedMarkerTooltipProps {
  annotation: CollapsedAnnotation
  x: number
  y: number
}

export function CollapsedMarkerTooltip({
  annotation,
  x,
  y,
}: CollapsedMarkerTooltipProps) {
  const { t } = useTranslation()
  const { date, count, buys, sells, annotations } = annotation

  return (
    <div
      className="absolute z-50 pointer-events-none bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-xs max-w-[280px]"
      style={{
        left: x,
        top: y,
        transform: 'translate(-50%, -100%) translateY(-12px)',
      }}
    >
      {/* Header */}
      <div className="font-semibold text-gray-900 mb-2 border-b border-gray-100 pb-1.5">
        {date}
      </div>

      {/* Summary */}
      <div className="flex items-center gap-3 mb-2 text-gray-600">
        <span className="font-medium">{t('component.charts.collapsed_marker_tooltip.trades_count', { count })}</span>
        {buys > 0 && <span className="text-green-600">{t('component.charts.collapsed_marker_tooltip.buys', { count: buys })}</span>}
        {sells > 0 && <span className="text-red-600">{t('component.charts.collapsed_marker_tooltip.sells', { count: sells })}</span>}
      </div>

      {/* Individual trades */}
      <div className="space-y-1 max-h-[160px] overflow-y-auto">
        {annotations.map((a, i) => (
          <div
            key={i}
            className="flex items-center justify-between gap-2 py-0.5"
          >
            <div className="flex items-center gap-1.5">
              <span
                className={`inline-block w-2 h-2 rounded-full ${
                  a.shape === 'arrowUp' ? 'bg-green-500' : 'bg-red-500'
                }`}
              />
              <span className="text-gray-700">{a.text}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

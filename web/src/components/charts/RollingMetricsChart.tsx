/**
 * RollingMetricsChart — Rolling window analytics chart with multiple configurable metrics.
 *
 * Used by:
 *  - OverviewTab for rolling Sharpe / Volatility
 *  - BenchmarkCompare for rolling Beta / Alpha
 */
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  CartesianGrid,
} from 'recharts'

export interface MetricConfig {
  key: string
  label: string
  color: string
}

export interface ReferenceLineConfig {
  value: number
  label?: string
  color?: string
}

export interface RollingMetricsChartProps {
  data: { date: string; values: Record<string, number> }[]
  metrics: MetricConfig[]
  window: number
  title?: string
  height?: number
  referenceLines?: ReferenceLineConfig[]
}

/** Flatten the nested values into a flat record for Recharts. */
function flattenData(data: RollingMetricsChartProps['data']) {
  return data.map(d => ({
    date: d.date,
    ...d.values,
  }))
}

/** Format a date string as MM-DD. */
function formatDate(dateStr: string): string {
  if (dateStr.length >= 10) return dateStr.slice(5, 10)
  return dateStr
}

/** Custom tooltip content. */
function TooltipContent({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ dataKey: string; value: number; color: string }>
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div className="bg-white rounded-lg shadow-lg border p-3 text-xs">
      <div className="font-medium text-gray-700 mb-1">{label}</div>
      {payload.map(item => (
        <div key={item.dataKey} className="flex items-center gap-2">
          <span
            className="inline-block w-2 h-2 rounded-full"
            style={{ backgroundColor: item.color }}
          />
          <span className="text-gray-600">{item.dataKey}</span>
          <span className="font-mono font-medium text-gray-800 ml-auto">
            {item.value != null && isFinite(item.value)
              ? item.value.toFixed(4)
              : '—'}
          </span>
        </div>
      ))}
    </div>
  )
}

export function RollingMetricsChart({
  data,
  metrics,
  window: windowSize,
  title,
  height = 250,
  referenceLines,
}: RollingMetricsChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-sm border p-4">
        {title && (
          <div className="text-sm font-semibold text-gray-800 mb-2">
            {title}
            <span className="text-xs font-normal text-gray-400 ml-2">
              window={windowSize}
            </span>
          </div>
        )}
        <div
          className="flex items-center justify-center rounded-lg bg-gray-50 text-gray-400 text-sm"
          style={{ height }}
        >
          No rolling data available
        </div>
      </div>
    )
  }

  const flatData = flattenData(data)

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      {title && (
        <div className="text-sm font-semibold text-gray-800 mb-2">
          {title}
          <span className="text-xs font-normal text-gray-400 ml-2">
            window={windowSize}
          </span>
        </div>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={flatData}
          margin={{ top: 4, right: 16, left: -10, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10 }}
            interval="preserveStartEnd"
            tickFormatter={formatDate}
          />
          <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} />
          <Tooltip content={<TooltipContent />} />
          <Legend
            wrapperStyle={{ fontSize: 11 }}
            iconType="circle"
            iconSize={8}
          />
          {referenceLines?.map((ref, i) => (
            <ReferenceLine
              key={i}
              y={ref.value}
              stroke={ref.color ?? '#e5e7eb'}
              strokeDasharray="4 2"
              label={
                ref.label
                  ? {
                      value: ref.label,
                      position: 'right',
                      fontSize: 10,
                      fill: '#9ca3af',
                    }
                  : undefined
              }
            />
          ))}
          {metrics.map(m => (
            <Line
              key={m.key}
              type="monotone"
              dataKey={m.key}
              name={m.label}
              stroke={m.color}
              dot={false}
              strokeWidth={1.5}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

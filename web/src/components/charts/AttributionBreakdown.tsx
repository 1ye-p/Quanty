/**
 * AttributionBreakdown — Brinson attribution bar chart (allocation, selection, interaction effects).
 *
 * Uses Recharts BarChart with grouped or stacked bars.
 * Y-axis formatted as percentage.
 */
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  type TooltipProps,
} from 'recharts'

export interface AttributionEntry {
  name: string
  allocation_effect: number   // fraction, e.g. 0.02 = 2%
  selection_effect: number
  interaction_effect: number
}

interface Props {
  data: AttributionEntry[]
  stacked?: boolean
  title?: string
}

const COLORS = {
  allocation: '#3b82f6',   // blue-500
  selection: '#10b981',    // emerald-500
  interaction: '#f59e0b',  // amber-500
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

function AttributionTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white rounded-lg shadow-lg border border-gray-200 p-3 text-xs">
      <p className="font-semibold text-gray-700 mb-1.5">{label}</p>
      {payload.map(entry => (
        <div key={entry.name} className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
            <span className="text-gray-600">{entry.name}</span>
          </div>
          <span className="font-medium text-gray-800">{formatPct(entry.value ?? 0)}</span>
        </div>
      ))}
    </div>
  )
}

export function AttributionBreakdown({ data, stacked = false, title = 'Attribution Breakdown' }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-2">{title}</h3>
        <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
          No attribution data available
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <h3 className="font-semibold text-gray-800 mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
          />
          <YAxis
            tickFormatter={v => `${(v * 100).toFixed(1)}%`}
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
          />
          <Tooltip content={<AttributionTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 12 }}
            iconType="circle"
            iconSize={8}
          />
          <Bar
            dataKey="allocation_effect"
            name="Allocation"
            fill={COLORS.allocation}
            stackId={stacked ? 'attribution' : undefined}
            radius={stacked ? undefined : [4, 4, 0, 0]}
            maxBarSize={48}
          />
          <Bar
            dataKey="selection_effect"
            name="Selection"
            fill={COLORS.selection}
            stackId={stacked ? 'attribution' : undefined}
            radius={stacked ? undefined : [4, 4, 0, 0]}
            maxBarSize={48}
          />
          <Bar
            dataKey="interaction_effect"
            name="Interaction"
            fill={COLORS.interaction}
            stackId={stacked ? 'attribution' : undefined}
            radius={stacked ? [4, 4, 0, 0] : [4, 4, 0, 0]}
            maxBarSize={48}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

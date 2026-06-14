/**
 * PositionConcentration — Top-N position weights + HHI index.
 *
 * Shows stacked area chart of top 5/10/20 weights and an HHI gauge.
 * HHI legend: <1000 low concentration, 1000-1800 medium, >1800 high.
 */
import { useId } from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  type TooltipProps,
} from 'recharts'

export interface ConcentrationSnapshot {
  date: string               // YYYY-MM-DD
  top5_weight: number        // fraction, 0-1
  top10_weight: number
  top20_weight: number
  hhi: number                // Herfindahl index (0-10000)
}

interface Props {
  data: ConcentrationSnapshot[]
  title?: string
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

function hhiLevel(hhi: number): { label: string; color: string; bg: string } {
  if (hhi > 1800) return { label: 'High', color: 'text-red-600', bg: 'bg-red-50 border-red-200' }
  if (hhi > 1000) return { label: 'Medium', color: 'text-amber-600', bg: 'bg-amber-50 border-amber-200' }
  return { label: 'Low', color: 'text-green-600', bg: 'bg-green-50 border-green-200' }
}

function WeightTooltip({ active, payload, label }: TooltipProps<number, string>) {
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

function HHITooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const hhi = payload[0]?.value ?? 0
  const level = hhiLevel(hhi)
  return (
    <div className="bg-white rounded-lg shadow-lg border border-gray-200 p-3 text-xs">
      <p className="font-semibold text-gray-700 mb-1">{label}</p>
      <p className="text-gray-800">HHI: <span className="font-medium">{hhi.toFixed(0)}</span></p>
      <p className={`${level.color} font-medium`}>{level.label} Concentration</p>
    </div>
  )
}

export function PositionConcentration({ data, title = 'Position Concentration' }: Props) {
  const uid = useId()
  if (!data || data.length === 0) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-2">{title}</h3>
        <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
          No concentration data available
        </div>
      </div>
    )
  }

  const latest = data[data.length - 1]
  const level = hhiLevel(latest.hhi)

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800">{title}</h3>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs ${level.bg}`}>
          <span className="text-gray-500">HHI:</span>
          <span className="font-semibold text-gray-800">{latest.hhi.toFixed(0)}</span>
          <span className={`font-medium ${level.color}`}>({level.label})</span>
        </div>
      </div>

      {/* Weight distribution chart */}
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <defs>
            <linearGradient id={`${uid}-gradTop5`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.05} />
            </linearGradient>
            <linearGradient id={`${uid}-gradTop10`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#10b981" stopOpacity={0.05} />
            </linearGradient>
            <linearGradient id={`${uid}-gradTop20`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#f59e0b" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
          />
          <YAxis
            tickFormatter={v => `${(v * 100).toFixed(0)}%`}
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            domain={[0, 1]}
          />
          <Tooltip content={<WeightTooltip />} />
          <Legend wrapperStyle={{ fontSize: 12 }} iconType="circle" iconSize={8} />
          <Area
            type="monotone"
            dataKey="top20_weight"
            name="Top 20"
            stackId="weights"
            stroke="#f59e0b"
            fill={`url(#${uid}-gradTop20)`}
            strokeWidth={1.5}
          />
          <Area
            type="monotone"
            dataKey="top10_weight"
            name="Top 10"
            stackId="weights"
            stroke="#10b981"
            fill={`url(#${uid}-gradTop10)`}
            strokeWidth={1.5}
          />
          <Area
            type="monotone"
            dataKey="top5_weight"
            name="Top 5"
            stackId="weights"
            stroke="#3b82f6"
            fill={`url(#${uid}-gradTop5)`}
            strokeWidth={1.5}
          />
        </AreaChart>
      </ResponsiveContainer>

      {/* HHI series */}
      <div className="mt-6">
        <h4 className="text-sm font-medium text-gray-600 mb-2">HHI Index Over Time</h4>
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
            <defs>
              <linearGradient id="gradHHI" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: '#6b7280' }}
              axisLine={{ stroke: '#e5e7eb' }}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#6b7280' }}
              axisLine={{ stroke: '#e5e7eb' }}
            />
            <Tooltip content={<HHITooltip />} />
            {/* Reference lines for thresholds */}
            <Area
              type="monotone"
              dataKey="hhi"
              name="HHI"
              stroke="#8b5cf6"
              fill="url(#gradHHI)"
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
        {/* HHI Legend */}
        <div className="flex items-center justify-center gap-4 mt-2">
          <div className="flex items-center gap-1 text-xs">
            <div className="w-3 h-1 rounded bg-green-400" />
            <span className="text-gray-500">&lt;1000 Low</span>
          </div>
          <div className="flex items-center gap-1 text-xs">
            <div className="w-3 h-1 rounded bg-amber-400" />
            <span className="text-gray-500">1000-1800 Medium</span>
          </div>
          <div className="flex items-center gap-1 text-xs">
            <div className="w-3 h-1 rounded bg-red-400" />
            <span className="text-gray-500">&gt;1800 High</span>
          </div>
        </div>
      </div>
    </div>
  )
}

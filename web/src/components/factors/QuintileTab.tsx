/**
 * Quintile returns bar chart showing mean returns by quantile group.
 * Includes cumulative return chart and long-short spread chart.
 */
import { useMemo } from 'react'
import {
  ResponsiveContainer, BarChart, Bar, Cell,
  XAxis, YAxis, Tooltip, ReferenceLine,
  LineChart, Line, Legend,
  AreaChart, Area,
} from 'recharts'

interface QuintileTabProps {
  quantileReturns: { quantile: number; mean_return: number }[]
  cumulativeReturns?: { trade_date: string; [key: string]: number | string }[]
}

const QUINTILE_COLORS = {
  q1: '#16a34a', // dark green
  q2: '#86efac', // light green
  q3: '#9ca3af', // gray
  q4: '#fca5a5', // light red
  q5: '#dc2626', // dark red
} as const

export function QuintileTab({ quantileReturns, cumulativeReturns }: QuintileTabProps) {
  if (!quantileReturns || quantileReturns.length === 0) return null

  // Compute long-short spread data (Q1 - Q5)
  const spreadData = useMemo(() => {
    if (!cumulativeReturns || cumulativeReturns.length === 0) return []
    return cumulativeReturns.map(row => ({
      date: String(row.trade_date).slice(5), // MM-DD format
      spread: (row.q1 as number) - (row.q5 as number),
    }))
  }, [cumulativeReturns])

  // Final spread value for display
  const finalSpread = spreadData.length > 0 ? spreadData[spreadData.length - 1].spread : null

  // Format cumulative data with MM-DD dates
  const cumData = useMemo(() => {
    if (!cumulativeReturns || cumulativeReturns.length === 0) return []
    // Dynamically detect quintile keys (q1, q2, ... qN)
    const sample = cumulativeReturns[0]
    const quintileKeys = Object.keys(sample)
      .filter(k => k.startsWith('q') && k !== 'trade_date')
      .sort()
    return cumulativeReturns.map(row => {
      const entry: Record<string, unknown> = { date: String(row.trade_date).slice(5) }
      for (const k of quintileKeys) {
        entry[k.toUpperCase()] = row[k] as number
      }
      return entry
    })
  }, [cumulativeReturns])

  // Dynamically detect available quintile keys for chart lines
  const quintileKeys = useMemo(() => {
    if (!cumData.length) return []
    return Object.keys(cumData[0]).filter(k => k.startsWith('Q'))
  }, [cumData])

  return (
    <div className="space-y-4">
      {/* Mean Return Bar Chart */}
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <h3 className="font-semibold text-gray-800 mb-3 text-sm">Quantile Returns (5 groups)</h3>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={quantileReturns} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
            <XAxis dataKey="quantile" tick={{ fontSize: 11 }} tickFormatter={(v: number) => `Q${v}`} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
            <Tooltip formatter={(v: unknown) => `${((v as number) * 100).toFixed(3)}%`} />
            <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
            <Bar dataKey="mean_return" name="Mean Return" radius={[3, 3, 0, 0]}>
              {quantileReturns.map((entry) => (
                <Cell key={entry.quantile} fill={entry.mean_return >= 0 ? '#22c55e' : '#ef4444'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Cumulative Return Chart */}
      {cumData.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border p-4">
          <h3 className="font-semibold text-gray-800 mb-3 text-sm">Cumulative Quintile Returns</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={cumData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10 }}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 10 }}
                tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
              />
              <Tooltip
                formatter={(v: number) => `${(v * 100).toFixed(2)}%`}
                labelFormatter={(label: string) => `Date: ${label}`}
              />
              <Legend verticalAlign="top" height={32} />
              <ReferenceLine y={0} stroke="#e5e7eb" />
              {quintileKeys.map((qk, i) => (
                <Line
                  key={qk}
                  type="monotone"
                  dataKey={qk}
                  stroke={QUINTILE_COLORS[`q${i + 1}` as keyof typeof QUINTILE_COLORS] ?? '#94a3b8'}
                  dot={false}
                  strokeWidth={1.5}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Long-Short Spread Chart */}
      {spreadData.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-800 text-sm">Long-Short Spread (Q1 - Q5)</h3>
            {finalSpread !== null && (
              <span className={`text-sm font-medium ${finalSpread >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {(finalSpread * 100).toFixed(2)}%
              </span>
            )}
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={spreadData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10 }}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 10 }}
                tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`}
              />
              <Tooltip
                formatter={(v: number) => `${(v * 100).toFixed(2)}%`}
                labelFormatter={(label: string) => `Date: ${label}`}
              />
              <ReferenceLine y={0} stroke="#e5e7eb" />
              <Area
                type="monotone"
                dataKey="spread"
                name="Spread"
                stroke={finalSpread !== null && finalSpread >= 0 ? '#10b981' : '#ef4444'}
                fill={finalSpread !== null && finalSpread >= 0 ? '#d1fae5' : '#fecaca'}
                fillOpacity={0.6}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

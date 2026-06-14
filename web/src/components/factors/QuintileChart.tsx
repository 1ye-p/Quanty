/**
 * Quintile returns bar chart.
 * Shows Q1-Q5 mean returns as a bar chart with percentage formatting.
 */
import { ResponsiveContainer, BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ReferenceLine } from 'recharts'

interface QuintileChartProps {
  factorName: string
  groups: { quintile: string; mean_return: number; std_return?: number; count?: number }[]
  nGroups: number
}

export function QuintileChart({ factorName, groups, nGroups }: QuintileChartProps) {
  if (!groups || groups.length === 0) return null

  return (
    <div className="card">
      <h3 className="font-semibold text-gray-800 mb-3 text-sm">
        分层收益 — {factorName}（{nGroups} 分位）
      </h3>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={groups} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}>
          <XAxis dataKey="quintile" tickFormatter={v => `Q${v}`} tick={{ fontSize: 11 }} />
          <YAxis tickFormatter={v => `${(v * 100).toFixed(1)}%`} tick={{ fontSize: 11 }} />
          <Tooltip
            formatter={(v: number) => [`${(v * 100).toFixed(3)}%`, '均值收益']}
            labelFormatter={v => `第 ${v} 分位`}
          />
          <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
          <Bar dataKey="mean_return" radius={[4, 4, 0, 0]}>
            {groups.map((g, i) => (
              <Cell
                key={i}
                fill={Number(g.quintile) > Math.ceil(nGroups / 2)
                  ? `oklch(${50 + i * 4}% 0.18 145)`
                  : `oklch(${60 - i * 4}% 0.18 25)`}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

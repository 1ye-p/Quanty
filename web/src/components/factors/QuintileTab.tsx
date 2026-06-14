/**
 * Quintile returns bar chart showing mean returns by quantile group.
 */
import { ResponsiveContainer, BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ReferenceLine } from 'recharts'

interface QuintileTabProps {
  quantileReturns: { quantile: number; mean_return: number }[]
}

export function QuintileTab({ quantileReturns }: QuintileTabProps) {
  if (!quantileReturns || quantileReturns.length === 0) return null

  return (
    <div className="card">
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
  )
}

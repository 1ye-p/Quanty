/**
 * IC decay line chart.
 * Shows how IC decays over different lag periods.
 */
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine } from 'recharts'

interface DecayChartProps {
  factorName: string
  data: { lag: number; ic: number }[]
}

export function DecayChart({ factorName, data }: DecayChartProps) {
  if (!data || data.length === 0) return null

  return (
    <div className="card">
      <h3 className="font-semibold text-gray-800 mb-3 text-sm">
        Rank IC 衰减 — {factorName}（lag 1-10）
      </h3>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
          <XAxis dataKey="lag" tick={{ fontSize: 11 }} label={{ value: 'Lag', position: 'insideRight', fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v: unknown) => (v as number).toFixed(4)} />
          <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
          <Line type="monotone" dataKey="ic" stroke="#3b82f6" dot={{ r: 3 }} strokeWidth={2} name="IC" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

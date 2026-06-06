import { LineChart, Line, ResponsiveContainer } from 'recharts'

interface SparkLineProps {
  data: number[]
  color?: string
  height?: number
}

export function SparkLine({ data, color = '#4f63d2', height = 40 }: SparkLineProps) {
  if (!data.length) return null
  const chartData = data.map((v, i) => ({ i, v }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData}>
        <Line type="monotone" dataKey="v" stroke={color} dot={false} strokeWidth={1.5} />
      </LineChart>
    </ResponsiveContainer>
  )
}

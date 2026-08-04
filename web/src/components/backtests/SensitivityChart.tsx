import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { useTranslation } from 'react-i18next'

interface SensitivityChartProps {
  data: Record<string, any>[]
  paramKey: string
  metricKeys: string[]
  height?: number
}

export function SensitivityChart({ data, paramKey, metricKeys, height = 300 }: SensitivityChartProps) {
  const { t } = useTranslation()
  const colors = ['#4f63d2', '#22c55e', '#ef4444', '#f59e0b', '#8b5cf6']

  if (!data || data.length === 0) {
    return (
      <div className="card flex items-center justify-center h-48 text-gray-400 text-sm">
        {t('common.no_data')}
      </div>
    )
  }

  return (
    <div className="card p-4">
      <h4 className="text-sm font-medium text-gray-700 mb-3">{t('component.backtests.sensitivity.chart.title')}</h4>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis
            dataKey={paramKey}
            tick={{ fontSize: 11 }}
            label={{ value: paramKey, position: 'insideBottom', offset: -5, fontSize: 12 }}
          />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip
            contentStyle={{ fontSize: 12 }}
            formatter={(value: unknown, name: string) => [Number(value ?? 0).toFixed(4), name]}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {metricKeys.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={colors[i % colors.length]}
              strokeWidth={2}
              dot={{ r: 4 }}
              name={key}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

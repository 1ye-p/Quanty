import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { liveApi } from '@/lib/api/live'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

interface FundCurveProps {
  deploymentId: string
}

export function FundCurve({ deploymentId }: FundCurveProps) {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['live', 'pnl', deploymentId],
    queryFn: () => liveApi.pnl(deploymentId),
    refetchInterval: 30_000,
    enabled: !!deploymentId,
  })

  if (isLoading) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-4">{t('component.live.fund_curve.title')}</h3>
        <div className="h-64 flex items-center justify-center text-gray-400">
          {t('common.loading')}
        </div>
      </div>
    )
  }

  if (error || !data?.series || data.series.length === 0) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-4">{t('component.live.fund_curve.title')}</h3>
        <div className="h-64 flex items-center justify-center text-gray-400">
          {t('component.live.fund_curve.empty')}
        </div>
      </div>
    )
  }

  // Transform series into chart data
  const chartData = data.series.map((point: Record<string, unknown>) => ({
    date: String(point.date ?? point.time ?? '').slice(0, 10),
    nav: Number(point.nav ?? point.value ?? 0),
  }))

  return (
    <div className="card">
      <h3 className="font-semibold text-gray-800 mb-4">{t('component.live.fund_curve.title')}</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickFormatter={v => v.slice(5)}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              domain={['dataMin', 'dataMax']}
              tickFormatter={v => v.toFixed(2)}
            />
            <Tooltip
              labelFormatter={v => String(v)}
              formatter={(value: number) => [value.toFixed(4), 'NAV']}
            />
            <Line
              type="monotone"
              dataKey="nav"
              stroke="#4f63d2"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

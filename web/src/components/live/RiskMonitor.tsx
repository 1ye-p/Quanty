import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { liveApi } from '@/lib/api/live'

interface RiskMonitorProps {
  deploymentId: string
}

function MetricCard({
  label,
  value,
  warn,
  critical,
}: {
  label: string
  value: string
  warn?: boolean
  critical?: boolean
}) {
  const color = critical
    ? 'text-red-600 bg-red-50'
    : warn
      ? 'text-yellow-600 bg-yellow-50'
      : 'text-gray-800 bg-gray-50'
  return (
    <div className={`p-3 rounded-lg ${color}`}>
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-lg font-bold">{value}</div>
    </div>
  )
}

export function RiskMonitor({ deploymentId }: RiskMonitorProps) {
  const { t } = useTranslation()
  const { data, isLoading } = useQuery({
    queryKey: ['live', 'risk', deploymentId],
    queryFn: () => liveApi.risk(deploymentId),
    refetchInterval: 15_000,
    enabled: !!deploymentId,
  })

  if (isLoading) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-4">{t('component.live.risk_monitor.title')}</h3>
        <div className="text-gray-400 text-sm">{t('common.loading')}</div>
      </div>
    )
  }

  const snapshot = data?.latest_snapshot as Record<string, unknown> | null

  if (!snapshot) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-4">{t('component.live.risk_monitor.title')}</h3>
        <div className="text-center text-gray-400 py-8">{t('component.live.risk_monitor.empty')}</div>
      </div>
    )
  }

  const dailyPnl = Number(snapshot.daily_pnl ?? snapshot.dailyPnl ?? 0)
  const maxDrawdown = Number(snapshot.max_drawdown ?? snapshot.maxDrawdown ?? 0)
  const concentration = Number(snapshot.concentration ?? snapshot.top_concentration ?? 0)
  const turnover = Number(snapshot.turnover ?? snapshot.daily_turnover ?? 0)

  // Thresholds for color coding
  const dailyPnlWarn = Math.abs(dailyPnl) > 0.02
  const maxDdWarn = maxDrawdown > 0.05
  const maxDdCritical = maxDrawdown > 0.10
  const concentrationWarn = concentration > 0.30
  const concentrationCritical = concentration > 0.50
  const turnoverWarn = turnover > 0.20

  // Extract risk alerts from history or snapshot
  const alerts = (data?.history ?? [])
    .filter((h: Record<string, unknown>) => h.alert || h.warning || h.message)
    .slice(0, 5) as Record<string, unknown>[]

  return (
    <div className="card">
      <h3 className="font-semibold text-gray-800 mb-4">{t('component.live.risk_monitor.title')}</h3>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <MetricCard
          label={t('component.live.risk_monitor.label_daily_pnl')}
          value={`${dailyPnl >= 0 ? '+' : ''}${(dailyPnl * 100).toFixed(2)}%`}
          warn={dailyPnlWarn}
        />
        <MetricCard
          label={t('common.metric.max_drawdown')}
          value={`${(maxDrawdown * 100).toFixed(2)}%`}
          warn={maxDdWarn}
          critical={maxDdCritical}
        />
        <MetricCard
          label={t('component.live.risk_monitor.label_concentration')}
          value={`${(concentration * 100).toFixed(1)}%`}
          warn={concentrationWarn}
          critical={concentrationCritical}
        />
        <MetricCard
          label={t('component.live.risk_monitor.label_turnover')}
          value={`${(turnover * 100).toFixed(1)}%`}
          warn={turnoverWarn}
        />
      </div>

      {/* Risk alerts */}
      {alerts.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">{t('component.live.risk_monitor.alerts_title')}</h4>
          <div className="space-y-1.5 max-h-32 overflow-y-auto">
            {alerts.map((alert, idx) => (
              <div
                key={String(alert.id ?? alert.type ?? idx)}
                className="text-xs p-2 rounded bg-yellow-50 text-yellow-800 border border-yellow-200"
              >
                {String(alert.alert ?? alert.warning ?? alert.message)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

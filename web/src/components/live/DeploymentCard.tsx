import { useTranslation } from 'react-i18next'
import { type LiveDeployment } from '@/lib/api/live'

interface DeploymentCardProps {
  deployment: LiveDeployment
  selected: boolean
  onSelect: () => void
  onStop: () => void
  stopPending: boolean
}

export function DeploymentCard({
  deployment,
  selected,
  onSelect,
  onStop,
  stopPending,
}: DeploymentCardProps) {
  const { t } = useTranslation()
  const d = deployment
  const isActive = d.status === 'active'
  const pnl = d.metrics?.cagr ?? 0
  const pnlColor = pnl >= 0 ? 'text-red-600' : 'text-green-600'
  const borderColor = isActive ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-gray-50'
  const badgeColor = isActive ? 'bg-green-200 text-green-800' : 'bg-gray-200 text-gray-600'

  return (
    <div
      className={`p-4 rounded-lg border cursor-pointer transition-colors ${
        selected ? 'ring-2 ring-brand-500' : ''
      } ${borderColor}`}
      onClick={onSelect}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-gray-800">{d.strategy_id}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded-full ${badgeColor}`}>
            {isActive ? t('component.live.deployment.status_active') : t('component.live.deployment.status_stopped')}
          </span>
        </div>
        {isActive && (
          <button
            disabled={stopPending}
            onClick={e => {
              e.stopPropagation()
              if (!confirm(t('component.live.deployment.stop_confirm', { id: d.strategy_id }))) return
              onStop()
            }}
            className="btn-secondary text-xs disabled:opacity-50"
          >
            {stopPending ? t('component.live.deployment.btn_stopping') : t('component.live.deployment.btn_stop')}
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600">
        <div>
          <span className="text-gray-400">{t('page.live.stat.initial_cash')}：</span>
          <span>¥{d.initial_cash?.toLocaleString()}</span>
        </div>
        <div>
          <span className="text-gray-400">{t('page.live.stat.risk_mode')}：</span>
          <span>{d.risk_mode}</span>
        </div>
        <div>
          <span className="text-gray-400">{t('component.live.deployment.label_deployed_at')}</span>
          <span>{d.deployed_at?.slice(0, 10)}</span>
        </div>
        <div>
          <span className="text-gray-400">{t('page.live.stat.sharpe')}：</span>
          <span>{d.metrics?.sharpe != null ? Number(d.metrics.sharpe).toFixed(3) : '--'}</span>
        </div>
        {d.metrics?.cagr != null && (
          <div>
            <span className="text-gray-400">{t('page.live.stat.return_rate')}：</span>
            <span className={pnlColor}>
              {pnl >= 0 ? '+' : ''}{(pnl * 100).toFixed(2)}%
            </span>
          </div>
        )}
        {d.metrics?.max_drawdown != null && (
          <div>
            <span className="text-gray-400">{t('common.metric.max_drawdown')}：</span>
            <span className="text-red-600">
              {(Number(d.metrics.max_drawdown) * 100).toFixed(2)}%
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

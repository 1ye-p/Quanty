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
            {isActive ? '运行中' : '已停止'}
          </span>
        </div>
        {isActive && (
          <button
            disabled={stopPending}
            onClick={e => {
              e.stopPropagation()
              if (!confirm(`确认停止策略 ${d.strategy_id}？`)) return
              onStop()
            }}
            className="btn-secondary text-xs disabled:opacity-50"
          >
            {stopPending ? '停止中...' : '停止'}
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600">
        <div>
          <span className="text-gray-400">初始资金：</span>
          <span>¥{d.initial_cash?.toLocaleString()}</span>
        </div>
        <div>
          <span className="text-gray-400">风控：</span>
          <span>{d.risk_mode}</span>
        </div>
        <div>
          <span className="text-gray-400">部署时间：</span>
          <span>{d.deployed_at?.slice(0, 10)}</span>
        </div>
        <div>
          <span className="text-gray-400">Sharpe：</span>
          <span>{d.metrics?.sharpe != null ? Number(d.metrics.sharpe).toFixed(3) : '--'}</span>
        </div>
        {d.metrics?.cagr != null && (
          <div>
            <span className="text-gray-400">收益率：</span>
            <span className={pnlColor}>
              {pnl >= 0 ? '+' : ''}{(pnl * 100).toFixed(2)}%
            </span>
          </div>
        )}
        {d.metrics?.max_drawdown != null && (
          <div>
            <span className="text-gray-400">最大回撤：</span>
            <span className="text-red-600">
              {(Number(d.metrics.max_drawdown) * 100).toFixed(2)}%
            </span>
          </div>
        )}
      </div>

      <button
        onClick={e => {
          e.stopPropagation()
          onSelect()
        }}
        className="mt-2 text-xs text-brand-600 hover:text-brand-700"
      >
        查看详情 →
      </button>
    </div>
  )
}

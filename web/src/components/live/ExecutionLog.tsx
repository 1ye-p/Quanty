import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { liveApi, type LiveExecution } from '@/lib/api/live'

interface ExecutionLogProps {
  deploymentId: string
}

export function ExecutionLog({ deploymentId }: ExecutionLogProps) {
  const { t } = useTranslation()
  const { data, isLoading } = useQuery({
    queryKey: ['live', 'executions', deploymentId],
    queryFn: () => liveApi.getExecutions(deploymentId, 50),
    refetchInterval: 10_000,
    enabled: !!deploymentId,
  })

  if (isLoading) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-4">{t('component.live.execution_log.title')}</h3>
        <div className="text-gray-400 text-sm">{t('common.loading')}</div>
      </div>
    )
  }

  if (!data?.items || data.items.length === 0) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-4">{t('component.live.execution_log.title')}</h3>
        <div className="text-center text-gray-400 py-8">
          <div className="text-3xl mb-2">📋</div>
          <div>{t('component.live.execution_log.empty')}</div>
          <p className="text-xs mt-1">{t('component.live.execution_log.empty_hint')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800">
          {t('component.live.execution_log.title')}
          <span className="text-xs text-gray-500 ml-2">{t('component.live.execution_log.total_count', { count: data.total })}</span>
        </h3>
      </div>

      <div className="max-h-96 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
              <th className="table-th">{t('component.live.execution_log.col.time')}</th>
              <th className="table-th">{t('component.live.execution_log.col.asset')}</th>
              <th className="table-th">{t('component.live.execution_log.col.side')}</th>
              <th className="table-th text-right">{t('component.live.execution_log.col.qty')}</th>
              <th className="table-th text-right">{t('component.live.execution_log.col.price')}</th>
              <th className="table-th text-right">{t('component.live.execution_log.col.fee')}</th>
              <th className="table-th">{t('component.live.execution_log.col.status')}</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((ex: LiveExecution) => (
              <tr key={ex.execution_id} className="table-row">
                <td className="table-td text-gray-400">
                  {ex.executed_at?.slice(0, 16) ?? '--'}
                </td>
                <td className="table-td font-mono">{ex.asset_id}</td>
                <td className="table-td">
                  <span
                    className={`badge ${
                      ex.side === 'buy'
                        ? 'bg-red-100 text-red-800'
                        : 'bg-green-100 text-green-800'
                    }`}
                  >
                    {ex.side === 'buy' ? t('component.live.execution_log.side_buy') : t('component.live.execution_log.side_sell')}
                  </span>
                </td>
                <td className="table-td text-right">
                  {ex.filled_qty.toLocaleString()}
                </td>
                <td className="table-td text-right">
                  {ex.filled_price.toFixed(2)}
                </td>
                <td className="table-td text-right text-gray-500">
                  {ex.total_cost.toFixed(2)}
                </td>
                <td className="table-td">
                  <span
                    className={`badge ${
                      ex.status === 'filled'
                        ? 'bg-green-100 text-green-800'
                        : ex.status === 'rejected'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {ex.status === 'filled'
                      ? t('component.live.execution_log.status_filled')
                      : ex.status === 'rejected'
                        ? t('component.live.execution_log.status_rejected')
                        : ex.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

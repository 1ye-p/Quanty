import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { pipelineApi } from '@/lib/api/pipeline'
import { cn } from '@/lib/utils'
import { extendedQueryKeys } from '@/lib/queryKeys'

const statusColors: Record<string, string> = {
  running: 'bg-blue-100 text-blue-700',
  success: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  cancelled: 'bg-gray-100 text-gray-700',
}

export function ExecutionHistory() {
  const { t } = useTranslation()
  const { data: executions, isLoading, error } = useQuery({
    queryKey: extendedQueryKeys.pipeline.executions(),
    queryFn: () => pipelineApi.getExecutions(),
    refetchInterval: 30000,
    staleTime: 25_000,
  })

  const statusLabel = (status: string): string =>
    t(`component.pipeline.status.${status}`, { defaultValue: status })

  if (isLoading) return <div className="text-center py-4 text-gray-500">{t('common.loading')}</div>
  if (error) return <div className="text-center py-4 text-red-500">{t('component.pipeline.execution_history.load_failed')}</div>
  if (!executions?.length) return <div className="text-center py-8 text-gray-400">{t('component.pipeline.execution_history.empty')}</div>

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <h3 className="font-medium text-gray-800 mb-4">{t('component.pipeline.execution_history.title')}</h3>
      <div className="space-y-3">
        {executions.map(exec => (
          <div key={exec.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div>
              <div className="flex items-center gap-2">
                <span className={cn("text-xs px-2 py-0.5 rounded", statusColors[exec.status] ?? 'bg-gray-100 text-gray-700')}>
                  {statusLabel(exec.status)}
                </span>
                <span className="font-medium text-gray-800">{exec.id}</span>
              </div>
              <div className="text-sm text-gray-500 mt-1">
                {new Date(exec.started_at).toLocaleString('zh-CN')}
                {exec.completed_at && (
                  <span> → {new Date(exec.completed_at).toLocaleString('zh-CN')}</span>
                )}
              </div>
            </div>
            <div className="text-sm text-gray-500">
              {exec.duration_seconds && `${exec.duration_seconds}s`}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

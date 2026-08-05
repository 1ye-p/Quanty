/**
 * PipelineStatus — Displays pipeline run summary with auto-refresh.
 *
 * Fetches status via pipelineApi.getStatus() every 10 seconds.
 */
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { pipelineApi, type PipelineStatusResponse } from '@/lib/api'

const STATUS_BADGE: Record<string, string> = {
  success: 'bg-green-100 text-green-700',
  running: 'bg-blue-100 text-blue-700',
  error: 'bg-red-100 text-red-700',
  partial_failure: 'bg-red-100 text-red-700',
  idle: 'bg-gray-100 text-gray-500',
  started: 'bg-blue-100 text-blue-700',
  already_running: 'bg-blue-100 text-blue-700',
}

function badgeClass(status: string): string {
  return STATUS_BADGE[status] ?? 'bg-gray-100 text-gray-500'
}

export function PipelineStatus() {
  const { t } = useTranslation()
  const { data: status, isLoading } = useQuery<PipelineStatusResponse>({
    queryKey: ['pipeline', 'status'],
    queryFn: () => pipelineApi.status(),
    refetchInterval: 10_000,
  })

  const statusLabel = (status: string): string =>
    t(`component.pipeline.status.${status}`, { defaultValue: status })

  if (isLoading) {
    return (
      <div className="card p-4">
        <div className="text-sm text-gray-400">{t('component.pipeline.status_card.loading')}</div>
      </div>
    )
  }

  if (!status) {
    return (
      <div className="card p-4">
        <div className="text-sm text-gray-400">{t('component.pipeline.status_card.unavailable')}</div>
      </div>
    )
  }

  const stages = status.stages ?? {}
  const stageEntries = Object.entries(stages)
  const totalRuns = stageEntries.length
  const successCount = stageEntries.filter(([, s]) => s.status === 'success').length
  const failedCount = stageEntries.filter(([, s]) => s.status === 'error' || s.status === 'partial_failure').length
  const runningCount = stageEntries.filter(([, s]) => s.status === 'running' || s.status === 'started').length

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-medium text-gray-700">{t('component.pipeline.status_card.title')}</div>
        <span className={`badge ${badgeClass(status.status)}`}>
          {statusLabel(status.status)}
        </span>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-3 text-center">
        <div>
          <div className="text-lg font-bold text-gray-800">{totalRuns}</div>
          <div className="text-xs text-gray-400">{t('component.pipeline.status_card.total_stages')}</div>
        </div>
        <div>
          <div className="text-lg font-bold text-green-600">{successCount}</div>
          <div className="text-xs text-gray-400">{t('component.pipeline.status.success')}</div>
        </div>
        <div>
          <div className="text-lg font-bold text-red-600">{failedCount}</div>
          <div className="text-xs text-gray-400">{t('component.pipeline.status.error')}</div>
        </div>
        <div>
          <div className="text-lg font-bold text-blue-600">{runningCount}</div>
          <div className="text-xs text-gray-400">{t('component.pipeline.status.running')}</div>
        </div>
      </div>

      {/* Last run info */}
      {(status.run_id || status.started_at) && (
        <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-400 space-y-0.5">
          {status.run_id && <div>{t('component.pipeline.status_card.run_id')}: <span className="font-mono">{status.run_id}</span></div>}
          {status.started_at && (
            <div>
              {t('component.pipeline.status_card.started')}: {new Date(status.started_at).toLocaleString('zh-CN')}
              {status.finished_at && (
                <> &middot; {t('component.pipeline.status_card.finished')}: {new Date(status.finished_at).toLocaleString('zh-CN')}</>
              )}
              {status.duration_seconds != null && (
                <> &middot; {t('component.pipeline.status_card.duration')}: {status.duration_seconds.toFixed(1)}s</>
              )}
            </div>
          )}
          {status.detail && <div>{status.detail}</div>}
        </div>
      )}
    </div>
  )
}

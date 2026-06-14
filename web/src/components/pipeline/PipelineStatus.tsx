/**
 * PipelineStatus — Displays pipeline run summary with auto-refresh.
 *
 * Fetches status via pipelineApi.getStatus() every 10 seconds.
 */
import { useQuery } from '@tanstack/react-query'
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

const STATUS_LABEL: Record<string, string> = {
  success: '成功',
  running: '运行中',
  error: '失败',
  partial_failure: '部分失败',
  idle: '空闲',
  started: '已启动',
  already_running: '运行中',
}

function badgeClass(status: string): string {
  return STATUS_BADGE[status] ?? 'bg-gray-100 text-gray-500'
}

export function PipelineStatus() {
  const { data: status, isLoading } = useQuery<PipelineStatusResponse>({
    queryKey: ['pipeline', 'status'],
    queryFn: () => pipelineApi.status(),
    refetchInterval: 10_000,
  })

  if (isLoading) {
    return (
      <div className="card p-4">
        <div className="text-sm text-gray-400">加载管道状态...</div>
      </div>
    )
  }

  if (!status) {
    return (
      <div className="card p-4">
        <div className="text-sm text-gray-400">无法获取管道状态</div>
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
        <div className="text-sm font-medium text-gray-700">管道状态</div>
        <span className={`badge ${badgeClass(status.status)}`}>
          {STATUS_LABEL[status.status] ?? status.status}
        </span>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-3 text-center">
        <div>
          <div className="text-lg font-bold text-gray-800">{totalRuns}</div>
          <div className="text-xs text-gray-400">总阶段</div>
        </div>
        <div>
          <div className="text-lg font-bold text-green-600">{successCount}</div>
          <div className="text-xs text-gray-400">成功</div>
        </div>
        <div>
          <div className="text-lg font-bold text-red-600">{failedCount}</div>
          <div className="text-xs text-gray-400">失败</div>
        </div>
        <div>
          <div className="text-lg font-bold text-blue-600">{runningCount}</div>
          <div className="text-xs text-gray-400">运行中</div>
        </div>
      </div>

      {/* Last run info */}
      {(status.run_id || status.started_at) && (
        <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-400 space-y-0.5">
          {status.run_id && <div>运行 ID: <span className="font-mono">{status.run_id}</span></div>}
          {status.started_at && (
            <div>
              开始: {new Date(status.started_at).toLocaleString('zh-CN')}
              {status.finished_at && (
                <> &middot; 结束: {new Date(status.finished_at).toLocaleString('zh-CN')}</>
              )}
              {status.duration_seconds != null && (
                <> &middot; 耗时: {status.duration_seconds.toFixed(1)}s</>
              )}
            </div>
          )}
          {status.detail && <div>{status.detail}</div>}
        </div>
      )}
    </div>
  )
}

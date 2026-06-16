import { useQuery } from '@tanstack/react-query'
import { pipelineApi } from '@/lib/api/pipeline'
import { cn } from '@/lib/utils'
import { extendedQueryKeys } from '@/lib/queryKeys'

const statusColors: Record<string, string> = {
  running: 'bg-blue-100 text-blue-700',
  success: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  cancelled: 'bg-gray-100 text-gray-700',
}

const statusLabels: Record<string, string> = {
  running: '运行中',
  success: '成功',
  failed: '失败',
  cancelled: '已取消',
}

export function ExecutionHistory() {
  const { data: executions, isLoading, error } = useQuery({
    queryKey: extendedQueryKeys.pipeline.executions(),
    queryFn: () => pipelineApi.getExecutions(),
    refetchInterval: 30000,
    staleTime: 25_000,
  })

  if (isLoading) return <div className="text-center py-4 text-gray-500">加载中...</div>
  if (error) return <div className="text-center py-4 text-red-500">加载失败</div>
  if (!executions?.length) return <div className="text-center py-8 text-gray-400">暂无执行记录</div>

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <h3 className="font-medium text-gray-800 mb-4">执行历史</h3>
      <div className="space-y-3">
        {executions.map(exec => (
          <div key={exec.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div>
              <div className="flex items-center gap-2">
                <span className={cn("text-xs px-2 py-0.5 rounded", statusColors[exec.status] ?? 'bg-gray-100 text-gray-700')}>
                  {statusLabels[exec.status] ?? exec.status}
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

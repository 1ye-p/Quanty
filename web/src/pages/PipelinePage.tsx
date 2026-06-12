import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { pipelineApi, type PipelineStatusResponse } from '@/lib/api'

const STAGE_META: Record<string, { name: string; icon: string }> = {
  factors: { name: '因子计算', icon: '🧮' },
  ml: { name: '模型训练', icon: '🧠' },
  backtest: { name: '回测验证', icon: '📈' },
  analysis: { name: '分析报告', icon: '📊' },
  promotion: { name: '模型发布', icon: '🚀' },
}

const STATUS_LABELS: Record<string, string> = {
  success: '成功',
  running: '运行中',
  error: '失败',
  partial_failure: '部分失败',
  idle: '空闲',
  started: '已启动',
  already_running: '运行中',
  skipped: '跳过',
}

function statusBadgeClass(status: string): string {
  if (status === 'success') return 'bg-green-100 text-green-700'
  if (status === 'running' || status === 'started' || status === 'already_running')
    return 'bg-blue-100 text-blue-700'
  if (status === 'error' || status === 'partial_failure') return 'bg-red-100 text-red-700'
  if (status === 'skipped') return 'bg-yellow-100 text-yellow-700'
  return 'bg-gray-100 text-gray-500'
}

export function PipelinePage() {
  const queryClient = useQueryClient()

  const { data: status, isLoading } = useQuery<PipelineStatusResponse>({
    queryKey: ['pipeline', 'status'],
    queryFn: () => pipelineApi.status(),
    refetchInterval: 30_000,
  })

  const runMutation = useMutation({
    mutationFn: () => pipelineApi.run(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline'] })
    },
  })

  const overallStatus = status?.status ?? 'idle'
  const isRunning = overallStatus === 'running'
  const stages = status?.stages ?? {}

  // Build ordered stage list: known stages first, then any extras from the backend
  const knownKeys = Object.keys(STAGE_META)
  const allStageKeys = [
    ...knownKeys.filter((k) => k in stages),
    ...Object.keys(stages).filter((k) => !knownKeys.includes(k)),
  ]

  return (
    <div>
      <h1 className="page-title">自动化回测管道</h1>
      <p className="page-subtitle">端到端自动化：因子计算 → 模型训练 → 回测验证 → 分析报告 → 模型发布</p>

      {/* Status card */}
      <div className="card p-4 mb-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-gray-500">管道状态</div>
            <div className="flex items-center gap-2 mt-1">
              <span className={`badge ${statusBadgeClass(overallStatus)}`}>
                {STATUS_LABELS[overallStatus] ?? overallStatus}
              </span>
              {status?.run_id && (
                <span className="text-xs text-gray-400 font-mono">run: {status.run_id}</span>
              )}
            </div>
            {status?.detail && (
              <p className="text-sm text-gray-500 mt-1">{status.detail}</p>
            )}
            {status?.started_at && (
              <div className="text-xs text-gray-400 mt-1">
                开始: {new Date(status.started_at).toLocaleString('zh-CN')}
                {status.finished_at && (
                  <> &middot; 结束: {new Date(status.finished_at).toLocaleString('zh-CN')}</>
                )}
                {status.duration_seconds != null && (
                  <> &middot; 耗时: {status.duration_seconds.toFixed(1)}s</>
                )}
              </div>
            )}
          </div>
          <button
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending || isRunning}
            className="btn-primary"
          >
            {runMutation.isPending ? '提交中...' : isRunning ? '运行中...' : '立即运行'}
          </button>
        </div>
      </div>

      {/* Pipeline stages */}
      <div className="card p-4 mb-4">
        <div className="text-sm font-medium mb-3">管道阶段</div>
        {allStageKeys.length === 0 ? (
          <div className="text-center text-gray-400 py-4">
            {isLoading ? '加载中...' : '暂无阶段数据 — 请先运行管道'}
          </div>
        ) : (
          <div className="space-y-3">
            {allStageKeys.map((key) => {
              const meta = STAGE_META[key]
              const stage = stages[key]
              const stageStatus = stage?.status ?? 'pending'
              return (
                <div key={key} className="flex items-center gap-3">
                  <span className="text-lg">{meta?.icon ?? '⚙️'}</span>
                  <span className="text-sm font-medium flex-1">{meta?.name ?? key}</span>
                  <span className={`badge ${statusBadgeClass(stageStatus)}`}>
                    {STATUS_LABELS[stageStatus] ?? stageStatus}
                  </span>
                  {stage?.error && (
                    <span className="text-xs text-red-500 max-w-xs truncate" title={stage.error}>
                      {stage.error}
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* History placeholder — backend does not yet provide history */}
      <div className="card p-4">
        <div className="text-sm font-medium mb-3">历史记录</div>
        <div className="text-center text-gray-400 py-8">
          历史记录功能即将上线
        </div>
      </div>
    </div>
  )
}

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { pipelineApi } from '@/lib/api'

const PIPELINE_STEPS = [
  { key: 'data_ingest', name: '数据摄取', icon: '📥' },
  { key: 'factor_compute', name: '因子计算', icon: '🧮' },
  { key: 'ml_train', name: '模型训练', icon: '🧠' },
  { key: 'backtest', name: '回测验证', icon: '📈' },
  { key: 'report', name: '报告生成', icon: '📊' },
]

export function PipelinePage() {
  const queryClient = useQueryClient()

  const { data: status, isLoading } = useQuery({
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

  const lastRun = status?.last_run as string | undefined
  const lastStatus = status?.last_status as string | undefined
  const steps = (status?.steps ?? {}) as Record<string, { status: string; time?: string; detail?: string }>
  const history = (status?.history ?? []) as Array<{ run_id: string; started_at: string; status: string; duration?: string }>

  return (
    <div>
      <h1 className="page-title">自动化回测管道</h1>
      <p className="page-subtitle">端到端自动化：数据摄取 → 因子计算 → 模型训练 → 回测验证</p>

      {/* Status card */}
      <div className="card p-4 mb-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-gray-500">最后运行</div>
            <div className="text-lg font-semibold">
              {lastRun ? new Date(lastRun).toLocaleString('zh-CN') : '从未运行'}
            </div>
            {lastStatus && (
              <span className={`badge mt-1 ${lastStatus === 'success' ? 'bg-green-100 text-green-700' : lastStatus === 'running' ? 'bg-blue-100 text-blue-700' : 'bg-red-100 text-red-700'}`}>
                {lastStatus === 'success' ? '成功' : lastStatus === 'running' ? '运行中' : '失败'}
              </span>
            )}
          </div>
          <button
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending || lastStatus === 'running'}
            className="btn-primary"
          >
            {runMutation.isPending ? '提交中...' : '立即运行'}
          </button>
        </div>
      </div>

      {/* Pipeline steps */}
      <div className="card p-4 mb-4">
        <div className="text-sm font-medium mb-3">管道步骤</div>
        <div className="space-y-3">
          {PIPELINE_STEPS.map(step => {
            const stepData = steps[step.key]
            const stepStatus = stepData?.status ?? 'pending'
            return (
              <div key={step.key} className="flex items-center gap-3">
                <span className="text-lg">{step.icon}</span>
                <span className="text-sm font-medium flex-1">{step.name}</span>
                <span className={`badge ${stepStatus === 'done' ? 'bg-green-100 text-green-700' : stepStatus === 'running' ? 'bg-blue-100 text-blue-700' : stepStatus === 'error' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-500'}`}>
                  {stepStatus === 'done' ? '完成' : stepStatus === 'running' ? '运行中' : stepStatus === 'error' ? '失败' : '等待'}
                </span>
                {stepData?.time && (
                  <span className="text-xs text-gray-400">{stepData.time}</span>
                )}
                {stepData?.detail && (
                  <span className="text-xs text-gray-500 max-w-xs truncate">{stepData.detail}</span>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* History */}
      <div className="card p-4">
        <div className="text-sm font-medium mb-3">历史记录</div>
        {isLoading ? (
          <div className="text-center text-gray-400 py-8">加载中...</div>
        ) : history.length === 0 ? (
          <div className="text-center text-gray-400 py-8">暂无运行记录</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="table-row">
                  <th className="table-th">运行ID</th>
                  <th className="table-th">开始时间</th>
                  <th className="table-th">状态</th>
                  <th className="table-th">耗时</th>
                </tr>
              </thead>
              <tbody>
                {history.map((run, i) => (
                  <tr key={i} className="table-row">
                    <td className="table-td font-mono text-xs">{run.run_id?.slice(0, 12) ?? '-'}</td>
                    <td className="table-td">{run.started_at ? new Date(run.started_at).toLocaleString('zh-CN') : '-'}</td>
                    <td className="table-td">
                      <span className={`badge ${run.status === 'success' ? 'bg-green-100 text-green-700' : run.status === 'running' ? 'bg-blue-100 text-blue-700' : 'bg-red-100 text-red-700'}`}>
                        {run.status}
                      </span>
                    </td>
                    <td className="table-td text-gray-500">{run.duration ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

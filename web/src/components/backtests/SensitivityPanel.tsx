import { useState, useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { backtestsApi } from '@/lib/api'

interface SensitivityPanelProps {
  runId: string
  onComplete?: (result: any) => void
}

export function SensitivityPanel({ runId, onComplete }: SensitivityPanelProps) {
  const [paramName, setParamName] = useState('top_n')
  const [paramValues, setParamValues] = useState('5, 10, 15, 20')
  const [primaryMetric, setPrimaryMetric] = useState('sharpe_ratio')
  const [jobId, setJobId] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () => {
      const values = paramValues.split(',').map(v => {
        const n = Number(v.trim())
        return isNaN(n) ? v.trim() : n
      })
      return backtestsApi.runSensitivity(runId, {
        param_grid: { [paramName]: values },
        primary_metric: primaryMetric,
      })
    },
    onSuccess: (data) => {
      setJobId(data.job_id)
    },
  })

  // Poll for results
  const { data: result } = useQuery({
    queryKey: ['sensitivity-result', runId, jobId],
    queryFn: () => backtestsApi.getSensitivityResult(runId, jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data
      if (data?.status === 'completed' || data?.status === 'failed') return false
      return 2000
    },
  })

  const isRunning = mutation.isPending || (result?.status === 'running')
  const isComplete = result?.status === 'completed'
  const isFailed = result?.status === 'failed'

  // Invoke onComplete callback when results arrive
  useEffect(() => {
    if (isComplete && result?.result && onComplete) {
      onComplete(result.result)
    }
  }, [isComplete, result?.result, onComplete])

  return (
    <div className="card space-y-4">
      <h3 className="font-semibold text-gray-900">参数敏感性分析</h3>

      {/* Configuration */}
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">参数名</label>
          <select
            value={paramName}
            onChange={e => setParamName(e.target.value)}
            className="input-field text-sm w-full"
          >
            <option value="top_n">top_n</option>
            <option value="rebalance_frequency">rebalance_frequency</option>
            <option value="stop_loss">stop_loss</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">参数值（逗号分隔）</label>
          <input
            type="text"
            value={paramValues}
            onChange={e => setParamValues(e.target.value)}
            className="input-field text-sm w-full"
            placeholder="5, 10, 15, 20"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">优化指标</label>
          <select
            value={primaryMetric}
            onChange={e => setPrimaryMetric(e.target.value)}
            className="input-field text-sm w-full"
          >
            <option value="sharpe_ratio">夏普比率</option>
            <option value="total_return">总收益</option>
            <option value="max_drawdown">最大回撤</option>
          </select>
        </div>
      </div>

      {/* Action */}
      <button
        onClick={() => mutation.mutate()}
        disabled={isRunning || !paramValues.trim()}
        className="btn-primary disabled:opacity-50"
      >
        {isRunning ? '运行中...' : '运行扫描'}
      </button>

      {/* Status */}
      {isRunning && (
        <div className="text-sm text-blue-600">参数扫描运行中，请稍候...</div>
      )}
      {isFailed && (
        <div className="text-sm text-red-600">扫描失败: {result?.error}</div>
      )}
      {isComplete && result?.result && onComplete && (
        <div className="text-sm text-green-600">扫描完成</div>
      )}
    </div>
  )
}

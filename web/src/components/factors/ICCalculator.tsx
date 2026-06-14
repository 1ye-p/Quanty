/**
 * IC computation form.
 * Shows selected factors and computes IC matrix for them.
 */
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { factorAnalyticsApi } from '@/lib/api'
import { toast } from 'sonner'

interface ICCalculatorProps {
  selectedFactors: string[]
  featureSetVersion: string
  horizonDays: number
  onHorizonChange: (days: number) => void
  onJobCreated: (jobId: string) => void
}

export function ICCalculator({
  selectedFactors,
  featureSetVersion,
  horizonDays,
  onHorizonChange,
  onJobCreated,
}: ICCalculatorProps) {
  const navigate = useNavigate()

  const matrixMutation = useMutation({
    mutationFn: () =>
      factorAnalyticsApi.computeICMatrix({
        factor_names: selectedFactors,
        feature_set_version: featureSetVersion,
        horizon_days: horizonDays,
      }),
    onSuccess: (data) => {
      onJobCreated(data.job_id)
      toast.success('IC 矩阵计算已提交')
    },
    onError: (e: Error) => toast.error(`提交失败: ${e.message}`),
  })

  return (
    <div className="card">
      <h3 className="font-semibold text-gray-800 mb-3">IC 计算</h3>
      <div className="space-y-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">已选因子 ({selectedFactors.length})</label>
          <div className="flex flex-wrap gap-1 max-h-24 overflow-auto">
            {selectedFactors.length === 0 ? (
              <span className="text-xs text-gray-400">请在左侧选择因子</span>
            ) : (
              selectedFactors.map(f => (
                <span key={f} className="px-2 py-0.5 text-xs bg-blue-50 text-blue-700 rounded-full">{f}</span>
              ))
            )}
          </div>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Horizon</label>
          <select
            className="input w-full"
            value={horizonDays}
            onChange={e => onHorizonChange(Number(e.target.value))}
          >
            {[1, 2, 3, 5, 10, 20].map(d => (
              <option key={d} value={d}>{d} 天</option>
            ))}
          </select>
        </div>
        <button
          className="btn-primary w-full text-sm"
          disabled={selectedFactors.length < 2 || !featureSetVersion || matrixMutation.isPending}
          onClick={() => matrixMutation.mutate()}
        >
          {matrixMutation.isPending ? '计算中...' : '计算 IC 矩阵'}
        </button>
        {selectedFactors.length >= 2 && (
          <button
            className="btn-secondary w-full text-sm"
            onClick={() => navigate('/scoring', { state: { selectedFactors } })}
          >
            发送到打分
          </button>
        )}
      </div>
    </div>
  )
}

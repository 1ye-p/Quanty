/**
 * Modal for creating IC alert rules for a specific factor.
 */
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { alertsApi } from '@/lib/api'
import { toast } from 'sonner'

interface ICAlertModalProps {
  factorName: string
  defaultThreshold: number
  onClose: () => void
}

export function ICAlertModal({ factorName, defaultThreshold, onClose }: ICAlertModalProps) {
  const qc = useQueryClient()
  const [threshold, setThreshold] = useState(defaultThreshold)
  const [windowDays, setWindowDays] = useState(20)

  const createMutation = useMutation({
    mutationFn: (body: { rule_type: string; params: Record<string, unknown> }) =>
      alertsApi.createRule(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'rules'] })
      toast.success(`已为 ${factorName} 创建 IC 告警规则`)
      onClose()
    },
    onError: (e: Error) => toast.error(`创建失败: ${e.message}`),
  })

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="font-semibold text-gray-900">创建 IC 告警规则</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-2xl leading-none">&times;</button>
        </div>
        <div className="p-4 space-y-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">因子</label>
            <div className="font-mono text-sm bg-gray-50 px-2 py-1.5 rounded">{factorName}</div>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">IC 阈值（绝对值低于此值触发）</label>
            <input type="number" value={threshold} onChange={e => setThreshold(Number(e.target.value))}
              className="input w-full" min={0.001} max={0.1} step={0.005} />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">检查窗口（天）</label>
            <input type="number" value={windowDays} onChange={e => setWindowDays(Number(e.target.value))}
              className="input w-full" min={5} max={120} step={5} />
          </div>
        </div>
        <div className="flex justify-end gap-2 p-4 border-t">
          <button onClick={onClose} className="btn-secondary text-sm">取消</button>
          <button disabled={createMutation.isPending}
            onClick={() => createMutation.mutate({
              rule_type: 'factor_ic_low',
              params: { factor_name: factorName, threshold, window_days: windowDays },
            })}
            className="btn-primary text-sm disabled:opacity-50">
            {createMutation.isPending ? '创建中...' : '创建告警'}
          </button>
        </div>
      </div>
    </div>
  )
}

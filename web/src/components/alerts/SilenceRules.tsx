import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { alertsApi } from '@/lib/api'
import { toast } from 'sonner'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'

export function SilenceRules() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [duration, setDuration] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['alerts', 'silence-rules'],
    queryFn: alertsApi.silenceRules,
  })

  const createMutation = useMutation({
    mutationFn: async (body: { name: string; duration_minutes: number }) =>
      alertsApi.createSilenceRule(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'silence-rules'] })
      setShowForm(false)
      setName('')
      setDuration('')
      toast.success('静默规则已创建')
    },
    onError: (e: Error) => toast.error(`创建失败: ${e.message}`),
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => alertsApi.deleteSilenceRule(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'silence-rules'] })
      setDeleteTarget(null)
      toast.success('静默规则已删除')
    },
    onError: (e: Error) => toast.error(`删除失败: ${e.message}`),
  })

  const items = data?.items ?? []

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-800">
          静默规则（{items.length}）
        </h3>
        <button
          onClick={() => setShowForm(!showForm)}
          className="btn-secondary text-xs"
        >
          {showForm ? '收起' : '+ 新增'}
        </button>
      </div>

      {showForm && (
        <div className="mb-4 p-3 border rounded-lg bg-gray-50 space-y-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">规则名称</label>
            <input
              className="input w-full text-sm"
              placeholder="如：维护窗口"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">
              静默时长（分钟）
            </label>
            <input
              className="input w-full text-sm"
              type="number"
              min="1"
              placeholder="60"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
            />
          </div>
          <div className="flex gap-2 pt-1">
            <button
              onClick={() => {
                const mins = Number(duration)
                if (!name.trim() || !mins || mins <= 0) {
                  toast.error('请填写名称和有效的时长')
                  return
                }
                createMutation.mutate({
                  name: name.trim(),
                  duration_minutes: mins,
                })
              }}
              disabled={createMutation.isPending}
              className="btn-primary text-xs disabled:opacity-50"
            >
              {createMutation.isPending ? '创建中...' : '创建'}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="btn-secondary text-xs"
            >
              取消
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-gray-200 rounded w-3/4" />
          <div className="h-4 bg-gray-200 rounded w-1/2" />
        </div>
      ) : items.length === 0 ? (
        <p className="text-sm text-gray-400 py-4 text-center">暂无静默规则</p>
      ) : (
        <ul className="space-y-2">
          {items.map((rule) => (
            <li
              key={rule.rule_id}
              className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50"
            >
              <div>
                <div className="text-sm font-medium text-gray-800">
                  {rule.name}
                </div>
                <div className="text-xs text-gray-500">
                  静默 {rule.duration_minutes} 分钟
                </div>
              </div>
              <button
                onClick={() => setDeleteTarget(rule.rule_id)}
                className="text-xs text-red-500 hover:underline"
              >
                删除
              </button>
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title="确认删除静默规则"
        message="确定删除此静默规则？此操作不可撤销。"
        confirmLabel="删除"
        variant="danger"
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget)
        }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}

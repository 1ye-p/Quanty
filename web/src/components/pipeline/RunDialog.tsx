import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { pipelineApi } from '@/lib/api/pipeline'

interface RunDialogProps {
  open: boolean
  onClose: () => void
  initialParams?: Record<string, Record<string, unknown>>
}

export function RunDialog({ open, onClose, initialParams }: RunDialogProps) {
  const queryClient = useQueryClient()
  const [paramsText, setParamsText] = useState(() =>
    initialParams ? JSON.stringify({ node_configs: initialParams }, null, 2) : '{}'
  )
  const [parseError, setParseError] = useState(false)

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  const runMutation = useMutation({
    mutationFn: (params: Record<string, unknown>) => pipelineApi.run(params),
    onSuccess: () => {
      toast.success('管道已触发')
      queryClient.invalidateQueries({ queryKey: ['pipeline'] })
      onClose()
    },
    onError: (e: Error) => toast.error(`触发失败: ${e.message}`),
  })

  if (!open) return null

  const handleRun = () => {
    try {
      const params = JSON.parse(paramsText)
      setParseError(false)
      runMutation.mutate(params)
    } catch {
      setParseError(true)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white rounded-lg p-6 w-96" onClick={e => e.stopPropagation()}>
        <h3 className="font-medium text-gray-800 mb-4">运行管道</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">参数 (JSON)</label>
            <textarea
              value={paramsText}
              onChange={e => {
                setParamsText(e.target.value)
                setParseError(false)
              }}
              className="w-full border rounded-lg p-2 text-sm font-mono"
              rows={4}
              placeholder='{"node_configs": {}}'
            />
            {parseError && <p className="text-xs text-red-500 mt-1">JSON 格式错误</p>}
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleRun}
              disabled={runMutation.isPending}
              className="btn-primary flex-1 disabled:opacity-50"
            >
              {runMutation.isPending ? '触发中...' : '运行'}
            </button>
            <button onClick={onClose} className="btn-secondary flex-1">
              取消
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

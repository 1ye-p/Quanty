import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { pipelineApi } from '@/lib/api/pipeline'
import { extendedQueryKeys } from '@/lib/queryKeys'

interface RunDialogProps {
  open: boolean
  onClose: () => void
  initialParams?: Record<string, Record<string, unknown>>
}

export function RunDialog({ open, onClose, initialParams }: RunDialogProps) {
  const { t } = useTranslation()
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
      toast.success(t('component.pipeline.run_dialog.triggered'))
      queryClient.invalidateQueries({ queryKey: extendedQueryKeys.pipeline.executions() })
      queryClient.invalidateQueries({ queryKey: extendedQueryKeys.pipeline.status() })
      onClose()
    },
    onError: (e: Error) => toast.error(t('component.pipeline.run_dialog.trigger_failed', { message: e.message })),
  })

  if (!open) return null

  const handleRun = () => {
    try {
      const parsed = JSON.parse(paramsText)
      setParseError(false)
      // Ensure the payload has the expected structure
      const body = parsed.node_configs ? parsed : { node_configs: parsed }
      runMutation.mutate(body)
    } catch {
      setParseError(true)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white rounded-lg p-6 w-96" onClick={e => e.stopPropagation()}>
        <h3 className="font-medium text-gray-800 mb-4">{t('component.pipeline.run_dialog.title')}</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">{t('component.pipeline.run_dialog.params_label')}</label>
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
            {parseError && <p className="text-xs text-red-500 mt-1">{t('component.pipeline.run_dialog.json_error')}</p>}
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleRun}
              disabled={runMutation.isPending}
              className="btn-primary flex-1 disabled:opacity-50"
            >
              {runMutation.isPending ? t('component.pipeline.run_dialog.triggering') : t('component.pipeline.run_dialog.run')}
            </button>
            <button onClick={onClose} className="btn-secondary flex-1">
              {t('common.cancel')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

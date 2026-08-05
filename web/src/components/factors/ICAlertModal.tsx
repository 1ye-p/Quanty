/**
 * Modal for creating IC alert rules for a specific factor.
 */
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { alertsApi } from '@/lib/api'
import { toast } from 'sonner'

interface ICAlertModalProps {
  factorName: string
  defaultThreshold: number
  onClose: () => void
}

export function ICAlertModal({ factorName, defaultThreshold, onClose }: ICAlertModalProps) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [threshold, setThreshold] = useState(defaultThreshold)
  const [windowDays, setWindowDays] = useState(20)

  const createMutation = useMutation({
    mutationFn: (body: { rule_type: string; params: Record<string, unknown> }) =>
      alertsApi.createRule(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'rules'] })
      toast.success(t('component.factors.ic_alert_modal.toast_created', { name: factorName }))
      onClose()
    },
    onError: (e: Error) => toast.error(t('component.factors.ic_alert_modal.toast_create_failed', { message: e.message })),
  })

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="font-semibold text-gray-900">{t('component.factors.ic_alert_modal.title')}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-2xl leading-none">&times;</button>
        </div>
        <div className="p-4 space-y-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">{t('component.factors.ic_alert_modal.label_factor')}</label>
            <div className="font-mono text-sm bg-gray-50 px-2 py-1.5 rounded">{factorName}</div>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">{t('component.factors.ic_alert_modal.label_threshold')}</label>
            <input type="number" value={threshold} onChange={e => setThreshold(Number(e.target.value))}
              className="input w-full" min={0.001} max={0.1} step={0.005} />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">{t('component.factors.ic_alert_modal.label_window')}</label>
            <input type="number" value={windowDays} onChange={e => setWindowDays(Number(e.target.value))}
              className="input w-full" min={5} max={120} step={5} />
          </div>
        </div>
        <div className="flex justify-end gap-2 p-4 border-t">
          <button onClick={onClose} className="btn-secondary text-sm">{t('component.factors.ic_alert_modal.btn_cancel')}</button>
          <button disabled={createMutation.isPending}
            onClick={() => createMutation.mutate({
              rule_type: 'factor_ic_low',
              params: { factor_name: factorName, threshold, window_days: windowDays },
            })}
            className="btn-primary text-sm disabled:opacity-50">
            {createMutation.isPending ? t('component.factors.ic_alert_modal.btn_creating') : t('component.factors.ic_alert_modal.btn_create')}
          </button>
        </div>
      </div>
    </div>
  )
}

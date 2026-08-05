import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { alertsApi } from '@/lib/api'
import { toast } from 'sonner'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'

export function SilenceRules() {
  const { t } = useTranslation()
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
      toast.success(t('component.alerts.silence_rules.created_toast'))
    },
    onError: (e: Error) => toast.error(t('component.alerts.silence_rules.create_failed', { message: e.message })),
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => alertsApi.deleteSilenceRule(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'silence-rules'] })
      setDeleteTarget(null)
      toast.success(t('component.alerts.silence_rules.deleted_toast'))
    },
    onError: (e: Error) => toast.error(t('component.alerts.silence_rules.delete_failed', { message: e.message })),
  })

  const items = data?.items ?? []

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-800">
          {t('component.alerts.silence_rules.title', { count: items.length })}
        </h3>
        <button
          onClick={() => setShowForm(!showForm)}
          className="btn-secondary text-xs"
        >
          {showForm ? t('component.alerts.silence_rules.collapse') : t('component.alerts.silence_rules.add_new')}
        </button>
      </div>

      {showForm && (
        <div className="mb-4 p-3 border rounded-lg bg-gray-50 space-y-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">{t('component.alerts.silence_rules.rule_name')}</label>
            <input
              className="input w-full text-sm"
              placeholder={t('component.alerts.silence_rules.rule_name_placeholder')}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">
              {t('component.alerts.silence_rules.duration_minutes')}
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
                  toast.error(t('component.alerts.silence_rules.validation_missing_fields'))
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
              {createMutation.isPending ? t('component.alerts.silence_rules.creating') : t('common.create')}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="btn-secondary text-xs"
            >
              {t('common.cancel')}
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
        <p className="text-sm text-gray-400 py-4 text-center">{t('component.alerts.silence_rules.no_rules')}</p>
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
                  {t('component.alerts.silence_rules.silence_duration', { minutes: rule.duration_minutes })}
                </div>
              </div>
              <button
                onClick={() => setDeleteTarget(rule.rule_id)}
                className="text-xs text-red-500 hover:underline"
              >
                {t('common.delete')}
              </button>
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title={t('component.alerts.silence_rules.confirm_delete_title')}
        message={t('component.alerts.silence_rules.confirm_delete_message')}
        confirmLabel={t('common.delete')}
        variant="danger"
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget)
        }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}

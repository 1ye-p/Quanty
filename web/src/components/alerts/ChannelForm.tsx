import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { alertsApi, type NotificationChannel } from '@/lib/api'
import { toast } from 'sonner'

interface ChannelFormProps {
  /** When provided, the form is in edit mode */
  channel?: NotificationChannel | null
  /** Called when form is cancelled or after successful save */
  onClose: () => void
}

/**
 * Per-type channel config field descriptors.
 * `labelKey` resolves via component.alerts.channel_form.* (or shared.* for shared labels).
 * `placeholder` stays a literal — it is example data (URLs / hosts), not user-facing copy.
 * `optional` marks non-required fields (drives validation).
 */
const CHANNEL_FORMS: Record<
  string,
  { key: string; labelKey: string; placeholder: string; optional?: boolean }[]
> = {
  webhook: [
    { key: 'url', labelKey: 'component.alerts.channel_form.webhook_url', placeholder: 'https://hooks.example.com/...' },
  ],
  email: [
    { key: 'smtp_host', labelKey: 'component.alerts.channel_form.smtp_host', placeholder: 'smtp.gmail.com' },
    { key: 'smtp_port', labelKey: 'component.alerts.channel_form.smtp_port', placeholder: '587' },
    { key: 'from_addr', labelKey: 'component.alerts.channel_form.from_addr', placeholder: 'alert@example.com' },
    {
      key: 'to_addrs',
      labelKey: 'component.alerts.channel_form.to_addrs',
      placeholder: 'a@example.com,b@example.com',
    },
  ],
  dingtalk: [
    {
      key: 'webhook_url',
      labelKey: 'component.alerts.channel_form.dingtalk_webhook',
      placeholder: 'https://oapi.dingtalk.com/robot/send?access_token=...',
    },
    { key: 'secret', labelKey: 'component.alerts.channel_form.sign_secret_optional', placeholder: '', optional: true },
  ],
}

export function ChannelForm({ channel, onClose }: ChannelFormProps) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const isEdit = !!channel

  const [chType, setChType] = useState(channel?.channel_type ?? 'webhook')
  const [chName, setChName] = useState(channel?.name ?? '')
  const [chConfig, setChConfig] = useState<Record<string, string>>(() => {
    if (!channel) return {}
    // Flatten config values to strings
    const result: Record<string, string> = {}
    for (const [k, v] of Object.entries(channel.config)) {
      result[k] = Array.isArray(v) ? v.join(', ') : String(v)
    }
    return result
  })

  // Reset config fields when type changes (only in create mode)
  useEffect(() => {
    if (!isEdit) setChConfig({})
  }, [chType, isEdit])

  const createMutation = useMutation({
    mutationFn: async (body: { channel_type: string; name: string; config: Record<string, unknown>; enabled?: boolean }) =>
      alertsApi.createChannel(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'channels'] })
      toast.success(t('component.alerts.channel_form.created_toast'))
      onClose()
    },
    onError: (e: Error) => toast.error(t('component.alerts.channel_form.create_failed', { message: e.message })),
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      alertsApi.updateChannel(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'channels'] })
      toast.success(t('component.alerts.channel_form.updated_toast'))
      onClose()
    },
    onError: (e: Error) => toast.error(t('component.alerts.channel_form.update_failed', { message: e.message })),
  })

  const fields = CHANNEL_FORMS[chType] ?? []
  const isPending = createMutation.isPending || updateMutation.isPending

  function buildConfig(): Record<string, unknown> {
    const config: Record<string, unknown> = {}
    for (const f of fields) {
      const v = chConfig[f.key] ?? ''
      if (f.key === 'to_addrs' && v) {
        config[f.key] = v
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
      } else if (f.key === 'smtp_port' && v) {
        config[f.key] = Number(v)
      } else if (v) {
        config[f.key] = v
      }
    }
    return config
  }

  function handleSubmit() {
    const config = buildConfig()
    // Validate required fields for the selected channel type
    const fields = CHANNEL_FORMS[chType] ?? []
    const requiredKeys = fields.filter(f => !f.optional).map(f => f.key)
    const missing = requiredKeys.filter(k => !config[k])
    if (missing.length > 0) {
      toast.error(t('component.alerts.channel_form.validation_missing_required', { fields: missing.join(', ') }))
      return
    }
    if (isEdit && channel) {
      updateMutation.mutate({
        id: channel.channel_id,
        body: { name: chName, config },
      })
    } else {
      createMutation.mutate({
        channel_type: chType,
        name: chName,
        config,
      })
    }
  }

  return (
    <div className="space-y-3">
      <h3 className="font-semibold text-gray-800">
        {isEdit ? t('component.alerts.channel_form.edit_title') : t('component.alerts.channel_form.create_title')}
      </h3>

      <div>
        <label className="block text-xs text-gray-600 mb-1">{t('component.alerts.shared.channel_type')}</label>
        <select
          value={chType}
          onChange={(e) => setChType(e.target.value)}
          disabled={isEdit}
          className="input w-full text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <option value="webhook">{t('component.alerts.shared.channel_types.webhook')}</option>
          <option value="email">{t('component.alerts.shared.channel_types.email')}</option>
          <option value="dingtalk">{t('component.alerts.shared.channel_types.dingtalk')}</option>
        </select>
      </div>

      <div>
        <label className="block text-xs text-gray-600 mb-1">{t('component.alerts.shared.name')}</label>
        <input
          className="input w-full text-sm"
          placeholder={t('component.alerts.channel_form.name_placeholder')}
          value={chName}
          onChange={(e) => setChName(e.target.value)}
        />
      </div>

      {fields.map((f) => (
        <div key={f.key}>
          <label className="block text-xs text-gray-600 mb-1">{t(f.labelKey)}</label>
          <input
            className="input w-full text-sm"
            placeholder={f.placeholder}
            value={chConfig[f.key] ?? ''}
            onChange={(e) =>
              setChConfig((p) => ({ ...p, [f.key]: e.target.value }))
            }
          />
        </div>
      ))}

      <div className="flex gap-2 pt-2">
        <button
          onClick={handleSubmit}
          disabled={isPending || !chName.trim()}
          className="btn-primary text-sm disabled:opacity-50"
        >
          {isPending
            ? (isEdit ? t('component.alerts.channel_form.updating') : t('component.alerts.channel_form.creating'))
            : (isEdit ? t('common.save') : t('common.create'))}
        </button>
        <button onClick={onClose} className="btn-secondary text-sm">
          {t('common.cancel')}
        </button>
      </div>
    </div>
  )
}

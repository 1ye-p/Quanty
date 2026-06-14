import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { alertsApi, type NotificationChannel } from '@/lib/api'
import { toast } from 'sonner'

interface ChannelFormProps {
  /** When provided, the form is in edit mode */
  channel?: NotificationChannel | null
  /** Called when form is cancelled or after successful save */
  onClose: () => void
}

const CHANNEL_FORMS: Record<
  string,
  { key: string; label: string; placeholder: string }[]
> = {
  webhook: [
    { key: 'url', label: 'Webhook URL', placeholder: 'https://hooks.example.com/...' },
  ],
  email: [
    { key: 'smtp_host', label: 'SMTP 服务器', placeholder: 'smtp.gmail.com' },
    { key: 'smtp_port', label: '端口', placeholder: '587' },
    { key: 'from_addr', label: '发件人', placeholder: 'alert@example.com' },
    {
      key: 'to_addrs',
      label: '收件人（逗号分隔）',
      placeholder: 'a@example.com,b@example.com',
    },
  ],
  dingtalk: [
    {
      key: 'webhook_url',
      label: '机器人 Webhook',
      placeholder: 'https://oapi.dingtalk.com/robot/send?access_token=...',
    },
    { key: 'secret', label: '签名密钥（可选）', placeholder: '' },
  ],
}

export function ChannelForm({ channel, onClose }: ChannelFormProps) {
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
      toast.success('通知渠道已创建')
      onClose()
    },
    onError: (e: Error) => toast.error(`创建失败: ${e.message}`),
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      alertsApi.updateChannel(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'channels'] })
      toast.success('通知渠道已更新')
      onClose()
    },
    onError: (e: Error) => toast.error(`更新失败: ${e.message}`),
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
        {isEdit ? '编辑通知渠道' : '新增通知渠道'}
      </h3>

      <div>
        <label className="block text-xs text-gray-600 mb-1">渠道类型</label>
        <select
          value={chType}
          onChange={(e) => setChType(e.target.value)}
          disabled={isEdit}
          className="input w-full text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <option value="webhook">Webhook</option>
          <option value="email">邮件</option>
          <option value="dingtalk">钉钉</option>
        </select>
      </div>

      <div>
        <label className="block text-xs text-gray-600 mb-1">名称</label>
        <input
          className="input w-full text-sm"
          placeholder="如：运维告警群"
          value={chName}
          onChange={(e) => setChName(e.target.value)}
        />
      </div>

      {fields.map((f) => (
        <div key={f.key}>
          <label className="block text-xs text-gray-600 mb-1">{f.label}</label>
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
          {isPending ? '保存中...' : isEdit ? '更新' : '创建'}
        </button>
        <button onClick={onClose} className="btn-secondary text-sm">
          取消
        </button>
      </div>
    </div>
  )
}

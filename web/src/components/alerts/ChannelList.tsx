import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { alertsApi, type NotificationChannel } from '@/lib/api'
import { toast } from 'sonner'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { useState } from 'react'

interface ChannelListProps {
  onEdit: (channel: NotificationChannel) => void
}

const CHANNEL_ICONS: Record<string, string> = {
  webhook: '🔗',
  email: '📧',
  dingtalk: '📢',
}

function channelTypeLabel(type: string): string {
  const map: Record<string, string> = {
    webhook: 'Webhook',
    email: '邮件',
    dingtalk: '钉钉',
  }
  return map[type] ?? type
}

export function ChannelList({ onEdit }: ChannelListProps) {
  const qc = useQueryClient()
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['alerts', 'channels'],
    queryFn: alertsApi.channels,
  })

  const toggleMutation = useMutation({
    mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) =>
      alertsApi.updateChannel(id, { enabled }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'channels'] })
      toast.success('渠道状态已更新')
    },
    onError: (e: Error) => toast.error(`更新失败: ${e.message}`),
  })

  const testMutation = useMutation({
    mutationFn: async (id: string) => alertsApi.testChannel(id),
    onSuccess: (d) => toast.success(d.message || '测试发送成功'),
    onError: (e: Error) => toast.error(`测试失败: ${e.message}`),
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => alertsApi.deleteChannel(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'channels'] })
      setDeleteTarget(null)
      toast.success('渠道已删除')
    },
    onError: (e: Error) => toast.error(`删除失败: ${e.message}`),
  })

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-3">
        <div className="h-4 bg-gray-200 rounded w-3/4" />
        <div className="h-4 bg-gray-200 rounded w-1/2" />
      </div>
    )
  }

  const items = data?.items ?? []

  return (
    <div>
      <h3 className="font-semibold text-gray-800 mb-3">
        通知渠道（{items.length}）
      </h3>

      {items.length === 0 ? (
        <p className="text-sm text-gray-400 py-6 text-center">
          暂无通知渠道，请在右侧创建
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map((ch) => (
            <li
              key={ch.channel_id}
              className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50"
            >
              <div className="flex items-center gap-3">
                <span className="text-lg">
                  {CHANNEL_ICONS[ch.channel_type] ?? '📢'}
                </span>
                <div>
                  <div className="text-sm font-medium text-gray-800">
                    {ch.name}
                  </div>
                  <div className="text-xs text-gray-500">
                    {channelTypeLabel(ch.channel_type)}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() =>
                    toggleMutation.mutate({
                      id: ch.channel_id,
                      enabled: !ch.enabled,
                    })
                  }
                  className={`text-xs px-2 py-1 rounded cursor-pointer ${
                    ch.enabled
                      ? 'bg-green-100 text-green-700 hover:bg-green-200'
                      : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                  }`}
                  title={ch.enabled ? '点击禁用' : '点击启用'}
                >
                  {ch.enabled ? '启用' : '禁用'}
                </button>
                <button
                  onClick={() => onEdit(ch)}
                  className="text-xs text-blue-500 hover:underline"
                >
                  编辑
                </button>
                <button
                  onClick={() => testMutation.mutate(ch.channel_id)}
                  disabled={testMutation.isPending}
                  className="text-xs text-amber-600 hover:underline disabled:opacity-50"
                >
                  测试
                </button>
                <button
                  onClick={() => setDeleteTarget(ch.channel_id)}
                  className="text-xs text-red-500 hover:underline"
                >
                  删除
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title="确认删除通知渠道"
        message="确定删除此通知渠道？此操作不可撤销。"
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

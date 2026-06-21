import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { alertsApi, type AlertRule, type NotificationChannel } from '@/lib/api'
import { toast } from 'sonner'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { ChannelList } from '@/components/alerts/ChannelList'
import { ChannelForm } from '@/components/alerts/ChannelForm'
import { SilenceRules } from '@/components/alerts/SilenceRules'

function severityBadge(severity: string) {
  const map: Record<string, { bg: string; text: string; label: string }> = {
    critical: { bg: 'bg-red-100', text: 'text-red-700', label: '严重' },
    warning:  { bg: 'bg-orange-100', text: 'text-orange-700', label: '警告' },
    info:     { bg: 'bg-blue-100', text: 'text-blue-700', label: '信息' },
  }
  const s = map[severity] ?? map.warning
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded ${s.bg} ${s.text}`}>
      {s.label}
    </span>
  )
}

export function AlertsPage() {
  const qc = useQueryClient()
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newRuleType, setNewRuleType] = useState('data_stale')
  const [newParams, setNewParams] = useState<Record<string, string>>({})
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  // Rule editing state
  const [editTarget, setEditTarget] = useState<AlertRule | null>(null)
  const [editParams, setEditParams] = useState<Record<string, string>>({})
  const [editEnabled, setEditEnabled] = useState(true)

  // Tab state
  type TabKey = 'rules' | 'history' | 'channels'
  const [activeTab, setActiveTab] = useState<TabKey>('rules')

  // Channel edit state (for the ChannelForm component)
  const [editingChannel, setEditingChannel] = useState<NotificationChannel | null>(null)
  const [showChannelForm, setShowChannelForm] = useState(false)

  const { data: rules } = useQuery({ queryKey: ['alerts', 'rules'], queryFn: alertsApi.rules })
  const { data: history } = useQuery({
    queryKey: ['alerts', 'history'],
    queryFn: () => alertsApi.history(false, 50),
    refetchInterval: 30_000,
  })

  const createMutation = useMutation({
    mutationFn: alertsApi.createRule,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'rules'] })
      setShowCreateForm(false)
      toast.success('告警规则已创建')
    },
    onError: (e: Error) => toast.error(`创建失败: ${e.message}`),
  })
  const deleteMutation = useMutation({
    mutationFn: alertsApi.deleteRule,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'rules'] })
      setDeleteTarget(null)
    },
    onError: (e: Error) => toast.error(`删除失败: ${e.message}`),
  })
  const updateMutation = useMutation({
    mutationFn: ({ ruleId, body }: { ruleId: string; body: Record<string, unknown> }) =>
      alertsApi.updateRule(ruleId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'rules'] })
      setEditTarget(null)
      toast.success('规则已更新')
    },
    onError: (e: Error) => toast.error(`更新失败: ${e.message}`),
  })
  const markReadMutation = useMutation({
    mutationFn: alertsApi.markAllRead,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'history'] })
      qc.invalidateQueries({ queryKey: ['alerts', 'unread-count'] })
    },
    onError: (e: Error) => toast.error(`标记已读失败: ${e.message}`),
  })
  const checkMutation = useMutation({
    mutationFn: alertsApi.check,
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['alerts', 'history'] })
      qc.invalidateQueries({ queryKey: ['alerts', 'unread-count'] })
      toast.info(`检查完成，触发 ${d.triggered} 条告警`)
    },
    onError: (e: Error) => toast.error(`告警检查失败: ${e.message}`),
  })
  const PARAM_FORMS: Record<string, { key: string; label: string; placeholder: string; defaultVal: string; options?: { value: string; label: string }[] }[]> = {
    data_stale:    [{ key: 'max_days', label: '最大允许天数', placeholder: '2', defaultVal: '2' }],
    factor_ic_low: [
      { key: 'factor_name', label: '因子名称', placeholder: 'ret_20d', defaultVal: '' },
      { key: 'threshold', label: 'IC 阈值（绝对值）', placeholder: '0.02', defaultVal: '0.02' },
      { key: 'window_days', label: '观察窗口（天）', placeholder: '20', defaultVal: '20' },
    ],
    pnl_drawdown: [
      { key: 'strategy_id', label: '策略 ID', placeholder: 'my_strategy', defaultVal: '' },
      { key: 'threshold_pct', label: '回撤阈值 (%)', placeholder: '10', defaultVal: '10' },
    ],
    news_sentiment: [
      { key: 'threshold', label: '情绪阈值', placeholder: '-0.5', defaultVal: '-0.5' },
      { key: 'change_threshold', label: '日变化阈值', placeholder: '-0.3', defaultVal: '-0.3' },
      {
        key: 'scope',
        label: '监控范围',
        placeholder: 'portfolio',
        defaultVal: 'portfolio',
        options: [
          { value: 'portfolio', label: '持仓' },
          { value: 'all', label: '全部' },
        ],
      },
    ],
    risk_breach: [],
  }

  const paramFields = PARAM_FORMS[newRuleType] ?? []

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'rules', label: '告警规则' },
    { key: 'history', label: '告警历史' },
    { key: 'channels', label: '通道配置' },
  ]

  function handleEditChannel(ch: NotificationChannel) {
    setEditingChannel(ch)
    setShowChannelForm(true)
  }

  function handleCloseChannelForm() {
    setEditingChannel(null)
    setShowChannelForm(false)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title">告警中心</h1>
          {history?.unread_count ? (
            <p className="page-subtitle text-red-500">{history.unread_count} 条未读告警</p>
          ) : (
            <p className="page-subtitle">无未读告警</p>
          )}
        </div>
        <div className="flex gap-2">
          <button onClick={() => checkMutation.mutate()} disabled={checkMutation.isPending}
            className="btn-secondary text-sm">立即检查</button>
          {(history?.unread_count ?? 0) > 0 && (
            <button onClick={() => markReadMutation.mutate()} className="btn-secondary text-sm">全部标为已读</button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`pb-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab: Rules */}
      {activeTab === 'rules' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={() => setShowCreateForm(true)} className="btn-primary text-sm">+ 新增规则</button>
          </div>

          {showCreateForm && (
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-4">新增告警规则</h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-gray-600 mb-1">规则类型</label>
                  <select value={newRuleType} onChange={e => { setNewRuleType(e.target.value); setNewParams({}) }}
                    className="input w-full text-sm">
                    {rules?.rule_types.map(rt => (
                      <option key={rt.type} value={rt.type}>{rt.label}</option>
                    ))}
                  </select>
                </div>
                {paramFields.map(f => (
                  <div key={f.key}>
                    <label className="block text-xs text-gray-600 mb-1">{f.label}</label>
                    {f.options ? (
                      <select
                        className="input w-full text-sm"
                        value={newParams[f.key] ?? f.defaultVal}
                        onChange={e => setNewParams(p => ({ ...p, [f.key]: e.target.value }))}
                      >
                        {f.options.map(o => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        className="input w-full text-sm"
                        placeholder={f.placeholder}
                        value={newParams[f.key] ?? f.defaultVal}
                        onChange={e => setNewParams(p => ({ ...p, [f.key]: e.target.value }))}
                      />
                    )}
                  </div>
                ))}
                <div className="flex gap-2 pt-2">
                  <button
                    onClick={() => {
                      const params: Record<string, unknown> = {}
                      for (const f of paramFields) {
                        const v = newParams[f.key] ?? f.defaultVal
                        params[f.key] = isNaN(Number(v)) || v === '' ? v : Number(v)
                      }
                      createMutation.mutate({ rule_type: newRuleType, params })
                    }}
                    disabled={createMutation.isPending}
                    className="btn-primary text-sm"
                  >
                    保存规则
                  </button>
                  <button onClick={() => setShowCreateForm(false)} className="btn-secondary text-sm">取消</button>
                </div>
              </div>
            </div>
          )}

          <div className="card">
            <h2 className="font-semibold text-gray-800 mb-3">告警规则（{rules?.items.length ?? 0}）</h2>
            {(rules?.items.length ?? 0) > 0 ? (
              <table className="w-full text-sm">
                <thead><tr className="text-left text-gray-500 border-b">
                  <th className="py-2">类型</th><th className="py-2">参数</th>
                  <th className="py-2 w-16">状态</th><th className="py-2 w-24">操作</th>
                </tr></thead>
                <tbody>
                  {rules!.items.map(r => (
                    <tr key={r.rule_id} className="border-b hover:bg-gray-50">
                      <td className="py-2">{r.rule_type_label}</td>
                      <td className="py-2 font-mono text-xs text-gray-500">{JSON.stringify(r.params)}</td>
                      <td className="py-2">
                        <span className={`text-xs px-1.5 py-0.5 rounded ${r.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                          {r.enabled ? '启用' : '禁用'}
                        </span>
                      </td>
                      <td className="py-2 flex gap-2">
                        <button onClick={() => {
                          setEditTarget(r)
                          setEditParams(Object.fromEntries(
                            Object.entries(r.params).map(([k, v]) => [k, String(v)])
                          ))
                          setEditEnabled(r.enabled)
                        }} className="text-xs text-blue-500 hover:underline">编辑</button>
                        <button onClick={() => setDeleteTarget(r.rule_id)}
                          className="text-xs text-red-500 hover:underline">删除</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-sm text-gray-400">暂无告警规则，点击"+ 新增规则"配置</p>
            )}
          </div>
        </div>
      )}

      {/* Tab: History */}
      {activeTab === 'history' && (
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-3">告警历史</h2>
          {(history?.items.length ?? 0) > 0 ? (
            <ul className="space-y-2">
              {history!.items.map(a => (
                <li key={a.alert_id}
                  className={`p-3 rounded-lg border text-sm ${a.read ? 'border-gray-200 bg-gray-50' : 'border-amber-300 bg-amber-50'}`}>
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-2">
                      {!a.read && <span className="w-2 h-2 rounded-full bg-amber-500 inline-block mt-1.5 flex-shrink-0" />}
                      {severityBadge(a.severity)}
                      <span className="text-gray-700">{a.message}</span>
                    </div>
                    <span className="text-xs text-gray-400 ml-3 flex-shrink-0">
                      {a.triggered_at.slice(0, 16).replace('T', ' ')}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-400">暂无告警历史</p>
          )}
        </div>
      )}

      {/* Tab: Channel Config */}
      {activeTab === 'channels' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card">
            <ChannelList onEdit={handleEditChannel} />
          </div>
          <div className="space-y-6">
            {showChannelForm ? (
              <div className="card">
                <ChannelForm channel={editingChannel} onClose={handleCloseChannelForm} />
              </div>
            ) : (
              <div className="card">
                <div className="flex justify-end mb-3">
                  <button onClick={() => setShowChannelForm(true)} className="btn-primary text-sm">
                    + 新增渠道
                  </button>
                </div>
              </div>
            )}
            <div className="card">
              <SilenceRules />
            </div>
          </div>
        </div>
      )}

      {/* Edit Rule Modal */}
      {editTarget && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="font-semibold text-gray-900">编辑告警规则</h2>
              <button onClick={() => setEditTarget(null)} className="text-gray-400 hover:text-gray-600">&times;</button>
            </div>
            <div className="p-4 space-y-3">
              <div>
                <label className="block text-xs text-gray-600 mb-1">规则类型</label>
                <div className="font-mono text-sm bg-gray-50 px-2 py-1.5 rounded">{editTarget.rule_type_label}</div>
              </div>
              {(PARAM_FORMS[editTarget.rule_type] ?? []).map(f => (
                <div key={f.key}>
                  <label className="block text-xs text-gray-600 mb-1">{f.label}</label>
                  {f.options ? (
                    <select
                      className="input w-full text-sm"
                      value={editParams[f.key] ?? ''}
                      onChange={e => setEditParams(p => ({ ...p, [f.key]: e.target.value }))}
                    >
                      {f.options.map(o => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      className="input w-full text-sm"
                      placeholder={f.placeholder}
                      value={editParams[f.key] ?? ''}
                      onChange={e => setEditParams(p => ({ ...p, [f.key]: e.target.value }))}
                    />
                  )}
                </div>
              ))}
              <div className="flex items-center gap-2">
                <input type="checkbox" id="edit-enabled" checked={editEnabled}
                  onChange={e => setEditEnabled(e.target.checked)} />
                <label htmlFor="edit-enabled" className="text-sm text-gray-700">启用</label>
              </div>
            </div>
            <div className="flex justify-end gap-2 p-4 border-t">
              <button onClick={() => setEditTarget(null)} className="btn-secondary text-sm">取消</button>
              <button
                disabled={updateMutation.isPending}
                onClick={() => {
                  const params: Record<string, unknown> = {}
                  for (const f of (PARAM_FORMS[editTarget.rule_type] ?? [])) {
                    const v = editParams[f.key] ?? ''
                    params[f.key] = isNaN(Number(v)) || v === '' ? v : Number(v)
                  }
                  updateMutation.mutate({
                    ruleId: editTarget.rule_id,
                    body: { params, enabled: editEnabled },
                  })
                }}
                className="btn-primary text-sm disabled:opacity-50"
              >
                {updateMutation.isPending ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title="确认删除规则"
        message="确定删除此告警规则？此操作不可撤销。"
        confirmLabel="删除"
        variant="danger"
        onConfirm={() => { if (deleteTarget) deleteMutation.mutate(deleteTarget) }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}

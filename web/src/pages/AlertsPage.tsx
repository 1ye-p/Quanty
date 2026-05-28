import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { alertsApi } from '@/lib/api'
import { toast } from 'sonner'

export function AlertsPage() {
  const qc = useQueryClient()
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newRuleType, setNewRuleType] = useState('data_stale')
  const [newParams, setNewParams] = useState<Record<string, string>>({})

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
  })
  const deleteMutation = useMutation({
    mutationFn: alertsApi.deleteRule,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts', 'rules'] }),
  })
  const markReadMutation = useMutation({
    mutationFn: alertsApi.markAllRead,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'history'] })
      qc.invalidateQueries({ queryKey: ['alerts', 'unread-count'] })
    },
  })
  const checkMutation = useMutation({
    mutationFn: alertsApi.check,
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['alerts', 'history'] })
      qc.invalidateQueries({ queryKey: ['alerts', 'unread-count'] })
      toast.info(`检查完成，触发 ${d.triggered} 条告警`)
    },
  })

  const PARAM_FORMS: Record<string, { key: string; label: string; placeholder: string; defaultVal: string }[]> = {
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
  }

  const paramFields = PARAM_FORMS[newRuleType] ?? []

  return (
    <div className="space-y-6">
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
          <button onClick={() => setShowCreateForm(true)} className="btn-primary text-sm">+ 新增规则</button>
        </div>
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
                <input
                  className="input w-full text-sm"
                  placeholder={f.placeholder}
                  value={newParams[f.key] ?? f.defaultVal}
                  onChange={e => setNewParams(p => ({ ...p, [f.key]: e.target.value }))}
                />
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
              <th className="py-2 w-16">状态</th><th className="py-2 w-16">操作</th>
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
                  <td className="py-2">
                    <button onClick={() => deleteMutation.mutate(r.rule_id)}
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

      <div className="card">
        <h2 className="font-semibold text-gray-800 mb-3">告警历史</h2>
        {(history?.items.length ?? 0) > 0 ? (
          <ul className="space-y-2">
            {history!.items.map(a => (
              <li key={a.alert_id}
                className={`p-3 rounded-lg border text-sm ${a.read ? 'border-gray-200 bg-gray-50' : 'border-amber-300 bg-amber-50'}`}>
                <div className="flex items-start justify-between">
                  <div>
                    {!a.read && <span className="w-2 h-2 rounded-full bg-amber-500 inline-block mr-2" />}
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
    </div>
  )
}

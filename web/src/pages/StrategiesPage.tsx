import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { strategiesApi, backtestsApi, datasetsApi } from '@/lib/api'
import { queryKeys, extendedQueryKeys } from '@/lib/queryKeys'
import Editor from '@monaco-editor/react'

const DEFAULT_CONFIG = JSON.stringify({
  strategy_id: "my_strategy",
  universe: { exchange: ["SSE", "SZSE"], min_liquidity: 1000000 },
  rebalance_frequency: "1d",
  risk_limits: { max_position_pct: 0.10, max_gross_leverage: 1.0 },
  factors: ["ret_20d", "vol_20d"],
  sizer: "equal_weight"
}, null, 2)

function BacktestRunModal({
  strategyId,
  configText,
  onClose,
}: {
  strategyId: string
  configText: string
  onClose: () => void
}) {
  const navigate = useNavigate()
  const parsed = useMemo(() => {
    try { return JSON.parse(configText) } catch { return {} }
  }, [configText])
  const factors: string[] = parsed.factors ?? ['ret_20d']
  const defaultTopN = parsed.top_n ?? 10

  const [startDate, setStartDate] = useState('2025-01-01')
  const [endDate, setEndDate] = useState('2025-06-30')
  const [topN, setTopN] = useState(String(defaultTopN))
  const [sortFactor, setSortFactor] = useState(factors[0])
  const [datasetVersion, setDatasetVersion] = useState('')

  const { data: datasets } = useQuery({
    queryKey: queryKeys.datasets.list(10),
    queryFn: () => datasetsApi.list(10),
  })

  // Auto-select current dataset
  useEffect(() => {
    if (datasets?.items.length && !datasetVersion) {
      const current = datasets.items.find(d => d.is_current) ?? datasets.items[0]
      setDatasetVersion(current.version_id)
    }
  }, [datasets, datasetVersion])

  const queryClient = useQueryClient()
  const runMutation = useMutation({
    mutationFn: backtestsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.backtests.all })
      onClose()
      navigate('/backtests')
    },
  })

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-[500px] max-w-[95vw]">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="font-semibold text-gray-900">执行回测</h2>
          <button className="text-gray-400 hover:text-gray-600" onClick={onClose}>✕</button>
        </div>
        <div className="p-4 space-y-4">
          <div>
            <label className="block text-sm text-gray-600 mb-1">策略</label>
            <div className="px-3 py-2 bg-gray-50 border rounded-lg text-sm">{strategyId}</div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">开始日期</label>
              <input type="date" className="input w-full" value={startDate} onChange={e => setStartDate(e.target.value)} />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">结束日期</label>
              <input type="date" className="input w-full" value={endDate} onChange={e => setEndDate(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Top N</label>
              <input type="number" className="input w-full" value={topN} onChange={e => setTopN(e.target.value)} min={1} />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">排序因子</label>
              <select className="input w-full" value={sortFactor} onChange={e => setSortFactor(e.target.value)}>
                {factors.map(f => <option key={f} value={f}>{f}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">数据集</label>
            <select className="input w-full" value={datasetVersion} onChange={e => setDatasetVersion(e.target.value)}>
              {datasets?.items.map(d => (
                <option key={d.version_id} value={d.version_id}>
                  {d.dataset_name} ({d.start_date} ~ {d.end_date}) — {d.asset_count ?? '?'} 股
                  {d.is_current ? ' ✓' : ''}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="flex justify-end gap-2 p-4 border-t">
          <button className="btn-secondary" onClick={onClose}>取消</button>
          <button
            className="btn-primary"
            disabled={runMutation.isPending || !datasetVersion}
            onClick={() => runMutation.mutate({
              strategy_id: strategyId,
              dataset_version: datasetVersion,
              start_date: startDate,
              end_date: endDate,
              top_n: Number(topN) || 10,
              sort_factor: sortFactor,
            })}
          >
            {runMutation.isPending ? '执行中…' : '执行回测'}
          </button>
        </div>
      </div>
    </div>
  )
}

export function StrategiesPage() {
  const qc = useQueryClient()
  const [editingId, setEditingId] = useState<string | 'new' | null>(null)
  const [configText, setConfigText] = useState(DEFAULT_CONFIG)
  const [newId, setNewId] = useState('')
  const [backtestStrategyId, setBacktestStrategyId] = useState<string | null>(null)
  const [backtestConfigText, setBacktestConfigText] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: extendedQueryKeys.strategies.list(),
    queryFn: strategiesApi.list,
  })

  const createMutation = useMutation({
    mutationFn: () => strategiesApi.create({ strategy_id: newId, config_text: configText }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: extendedQueryKeys.strategies.list() })
      setEditingId(null)
    },
  })

  const updateMutation = useMutation({
    mutationFn: (id: string) => strategiesApi.update(id, { config_text: configText }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: extendedQueryKeys.strategies.list() })
      setEditingId(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => strategiesApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: extendedQueryKeys.strategies.list() }),
  })

  function openEdit(item: { strategy_id: string; config_text: string }) {
    setEditingId(item.strategy_id)
    setConfigText(item.config_text)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">策略配置</h1>
          <p className="page-subtitle">创建和管理量化策略配置（JSON）</p>
        </div>
        <button className="btn-primary" onClick={() => { setEditingId('new'); setConfigText(DEFAULT_CONFIG); setNewId('') }}>
          + 新建策略
        </button>
      </div>

      {isLoading && <p className="text-gray-400">Loading…</p>}

      {/* Editor modal */}
      {editingId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-[700px] max-w-[95vw] max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="font-semibold text-gray-900">
                {editingId === 'new' ? '新建策略' : `编辑策略: ${editingId}`}
              </h2>
              <button className="text-gray-400 hover:text-gray-600" onClick={() => setEditingId(null)}>✕</button>
            </div>
            {editingId === 'new' && (
              <div className="p-4 border-b">
                <input
                  className="input"
                  placeholder="策略 ID（唯一标识符）"
                  value={newId}
                  onChange={e => setNewId(e.target.value)}
                />
              </div>
            )}
            <div className="flex-1 overflow-hidden">
              <Editor
                height="400px"
                language="json"
                value={configText}
                onChange={v => setConfigText(v ?? '')}
                options={{ minimap: { enabled: false }, fontSize: 13, scrollBeyondLastLine: false }}
              />
            </div>
            <div className="flex justify-end gap-2 p-4 border-t">
              <button className="btn-secondary" onClick={() => setEditingId(null)}>取消</button>
              <button
                className="btn-primary"
                disabled={createMutation.isPending || updateMutation.isPending}
                onClick={() => {
                  if (editingId === 'new') createMutation.mutate()
                  else updateMutation.mutate(editingId)
                }}
              >
                {(createMutation.isPending || updateMutation.isPending) ? '保存中…' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {!data?.items.length && !isLoading && (
          <div className="col-span-2 text-center text-gray-400 py-12">暂无策略，点击"新建策略"开始</div>
        )}
        {data?.items.map(s => (
          <div key={s.strategy_id} className="card">
            <div className="flex items-start justify-between">
              <div>
                <div className="font-semibold text-gray-900">{s.strategy_id}</div>
                <div className="text-xs text-gray-400 mt-1">更新于 {s.updated_at?.slice(0, 16) ?? '—'}</div>
              </div>
              <div className="flex gap-2">
                <button
                  className="btn-secondary text-xs px-3 py-1 text-green-600 border-green-300 hover:bg-green-50"
                  onClick={() => { setBacktestStrategyId(s.strategy_id); setBacktestConfigText(s.config_text) }}
                >▶ 回测</button>
                <button className="btn-secondary text-xs px-3 py-1" onClick={() => openEdit(s)}>编辑</button>
                <button
                  className="btn-danger text-xs px-3 py-1"
                  onClick={() => { if (confirm(`删除 ${s.strategy_id}?`)) deleteMutation.mutate(s.strategy_id) }}
                >删除</button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {backtestStrategyId && (
        <BacktestRunModal
          strategyId={backtestStrategyId}
          configText={backtestConfigText}
          onClose={() => setBacktestStrategyId(null)}
        />
      )}
    </div>
  )
}

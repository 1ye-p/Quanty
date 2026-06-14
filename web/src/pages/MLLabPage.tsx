import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { mlApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { ModelsTab } from '@/components/ml/ModelsTab'
import { ExperimentsTab } from '@/components/ml/ExperimentsTab'
import { PredictionsTab } from '@/components/ml/PredictionsTab'
import { TrainForm } from '@/components/ml/TrainForm'

type TabKey = 'models' | 'train' | 'experiments' | 'predictions'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'models', label: '模型库' },
  { key: 'train', label: '训练' },
  { key: 'experiments', label: '实验' },
  { key: 'predictions', label: '预测' },
]

export function MLLabPage() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<TabKey>('models')
  const [selectedRun, setSelectedRun] = useState<string | null>(null)
  const [compareRuns, setCompareRuns] = useState<string[]>([])
  const [predictRunId, setPredictRunId] = useState<string | null>(null)
  const [showPredictModal, setShowPredictModal] = useState(false)

  const { data: experiments, refetch } = useQuery({
    queryKey: extendedQueryKeys.ml.experiments(50),
    queryFn: () => mlApi.experiments(50),
  })

  const { data: modelsCatalog } = useQuery({
    queryKey: extendedQueryKeys.ml.modelsCatalog(),
    queryFn: () => mlApi.modelsCatalog(),
    staleTime: 300_000,
  })

  const groupedModels = useMemo(() => {
    if (!modelsCatalog) return []
    const groups: Record<string, { name: string; display_name: string; engine: string; description: string }[]> = {}
    const order = ['传统模型', '深度学习', '集成模型', '线性模型', '在线模型', '专用模型']
    for (const info of Object.values(modelsCatalog)) {
      const label = info.category_label || '其他'
      if (!groups[label]) groups[label] = []
      groups[label].push({
        name: info.name,
        display_name: info.display_name,
        engine: info.engine,
        description: info.description,
      })
    }
    return order
      .filter(label => groups[label])
      .map(label => ({ label, models: groups[label] }))
      .concat(
        Object.entries(groups)
          .filter(([label]) => !order.includes(label))
          .map(([label, models]) => ({ label, models }))
      )
  }, [modelsCatalog])

  const { data: fi } = useQuery({
    queryKey: extendedQueryKeys.ml.featureImportance(selectedRun ?? ''),
    queryFn: () => mlApi.featureImportance(selectedRun!),
    enabled: !!selectedRun,
  })

  const selectedExperiment = useMemo(() => {
    if (!selectedRun || !experiments?.items) return null
    return experiments.items.find(r => r.run_id === selectedRun) ?? null
  }, [selectedRun, experiments])

  const comparedExperiments = useMemo(() => {
    if (!experiments?.items || compareRuns.length < 2) return []
    return experiments.items.filter(r => compareRuns.includes(r.run_id))
  }, [experiments, compareRuns])

  const { data: predictResult, isFetching: predictFetching } = useQuery({
    queryKey: extendedQueryKeys.ml.predict(predictRunId!),
    queryFn: () => mlApi.predict({ model_version: predictRunId!, top_n: 30 }),
    enabled: !!predictRunId && showPredictModal,
    staleTime: 60_000,
  })

  return (
    <div>
      <h1 className="page-title">机器学习实验室</h1>
      <p className="page-subtitle">模型训练 · 实验对比 · 预测</p>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 border-b">
        {TABS.map(tab => (
          <button
            key={tab.key}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab: Models */}
      {activeTab === 'models' && <ModelsTab />}

      {/* Tab: Train */}
      {activeTab === 'train' && (
        <div className="flex gap-6">
          <div className="flex-1">
            <div className="card">
              <h2 className="font-semibold text-gray-800 mb-4">提交训练任务</h2>
              <TrainForm
                groupedModels={groupedModels}
                onSubmitted={() => { refetch(); setActiveTab('experiments') }}
              />
            </div>
          </div>
          <div className="w-80 flex-shrink-0">
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3 text-sm">工作流提示</h3>
              <ol className="text-xs text-gray-600 space-y-2 list-decimal list-inside">
                <li>选择 Feature Set 版本</li>
                <li>选择模型和超参数</li>
                <li>提交训练任务</li>
                <li>在"实验"标签页查看结果</li>
                <li>用模型创建交易策略</li>
              </ol>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Experiments */}
      {activeTab === 'experiments' && (
        <div>
          <div className="flex gap-6">
            <div className="flex-1">
              <ExperimentsTab
                selectedRun={selectedRun}
                onSelectRun={setSelectedRun}
                compareRuns={compareRuns}
                onToggleCompare={(runId) => setCompareRuns(prev =>
                  prev.includes(runId) ? prev.filter(id => id !== runId) : [...prev, runId]
                )}
                onCreateStrategy={(_runId, modelId) => navigate('/strategies', {
                  state: {
                    prefill: {
                      strategy_id: `ml_${modelId.slice(0, 8)}`,
                      config: JSON.stringify({
                        strategy_type: 'MLModelStrategy',
                        model_id: modelId,
                        top_n: 10,
                        label_name: 'ret_5d',
                      }, null, 2),
                    },
                  },
                })}
              />
            </div>

            {/* Feature Importance sidebar */}
            {selectedRun && fi && fi.items.length > 0 && (
              <div className="w-80">
                <h2 className="font-semibold text-gray-800 mb-3">特征重要性</h2>
                <div className="card">
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={[...fi.items].sort((a, b) => b.importance - a.importance).slice(0, 15)} layout="vertical">
                      <XAxis type="number" tick={{ fontSize: 10 }} />
                      <YAxis type="category" dataKey="feature" width={90} tick={{ fontSize: 10 }} />
                      <Tooltip />
                      <Bar dataKey="importance" fill="#4f63d2" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>

          {/* Experiment detail panel */}
          {selectedExperiment && (
            <div className="card mt-4">
              <h3 className="font-semibold text-gray-800 mb-3">执行详情</h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-gray-500">状态</span>
                  <div><StatusBadge status={selectedExperiment.status?.toLowerCase() ?? 'unknown'} /></div>
                </div>
                <div>
                  <span className="text-gray-500">Trainer</span>
                  <div className="font-medium">{selectedExperiment.trainer_name || '--'}</div>
                </div>
                <div>
                  <span className="text-gray-500">Target</span>
                  <div className="font-medium">{selectedExperiment.target_name || '--'}</div>
                </div>
                <div>
                  <span className="text-gray-500">Feature Set</span>
                  <div className="font-medium font-mono text-xs">{selectedExperiment.feature_set_version || '--'}</div>
                </div>
              </div>

              {selectedExperiment.params && Object.keys(selectedExperiment.params).length > 0 && (
                <div className="mt-3">
                  <span className="text-sm text-gray-500">训练参数</span>
                  <pre className="mt-1 p-2 bg-gray-50 rounded text-xs overflow-x-auto max-h-40">
                    {JSON.stringify(selectedExperiment.params, null, 2)}
                  </pre>
                </div>
              )}

              {selectedExperiment.metrics && Object.keys(selectedExperiment.metrics).length > 0 && (
                <div className="mt-3">
                  <span className="text-sm text-gray-500">训练指标</span>
                  <div className="grid grid-cols-3 gap-2 mt-1">
                    {Object.entries(selectedExperiment.metrics).map(([key, val]) => (
                      <div key={key} className="p-2 bg-gray-50 rounded text-center">
                        <div className="text-sm font-bold text-brand-600">
                          {typeof val === 'number' ? val.toFixed(4) : String(val)}
                        </div>
                        <div className="text-xs text-gray-500">{key}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selectedExperiment.status === 'error' && selectedExperiment.error_text && (
                <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
                  <span className="text-sm font-medium text-red-700">错误详情</span>
                  <pre className="mt-1 text-xs text-red-600 whitespace-pre-wrap">{selectedExperiment.error_text}</pre>
                </div>
              )}

              {(selectedExperiment.status === 'completed' || selectedExperiment.status === 'done') && selectedExperiment.model_id && (
                <div className="mt-3 flex justify-end gap-2">
                  <button className="btn-secondary text-sm"
                    onClick={() => { setPredictRunId(selectedExperiment.run_id); setShowPredictModal(true); setActiveTab('predictions') }}>
                    实时预测
                  </button>
                  <button className="btn-primary text-sm"
                    onClick={() => navigate(`/strategies?ml_model=${encodeURIComponent(selectedExperiment.run_id)}&strategy_type=MLModelStrategy&feature_set_version=${encodeURIComponent(selectedExperiment.feature_set_version ?? '')}&target_name=${encodeURIComponent(selectedExperiment.target_name ?? 'ret_5d')}`)}>
                    用此模型回测
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Model comparison panel */}
          {comparedExperiments.length >= 2 && (
            <div className="card mt-6">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold text-gray-800">模型对比（{comparedExperiments.length} 个）</h2>
                <button className="text-xs text-gray-400 hover:text-gray-600" onClick={() => setCompareRuns([])}>
                  清除选择
                </button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      {['指标', ...comparedExperiments.map(r => r.run_id.slice(0, 8) + '...')].map(h => (
                        <th key={h} className="table-th text-center">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      { label: 'Trainer', key: 'trainer', fmt: (r: typeof comparedExperiments[0]) => r.trainer_name || '--' },
                      { label: 'RMSE', key: 'rmse', fmt: (r: typeof comparedExperiments[0]) => r.metrics?.rmse?.toFixed(4) ?? '--' },
                      { label: 'Sharpe', key: 'sharpe', fmt: (r: typeof comparedExperiments[0]) => r.metrics?.sharpe?.toFixed(3) ?? '--' },
                    ].map(row => (
                      <tr key={row.key} className="table-row">
                        <td className="table-td font-medium text-gray-600">{row.label}</td>
                        {comparedExperiments.map(r => (
                          <td key={r.run_id} className="table-td text-center">{row.fmt(r)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab: Predictions */}
      {activeTab === 'predictions' && (
        selectedRun ? (
          <PredictionsTab runId={selectedRun} />
        ) : (
          <div className="card text-center py-8 text-gray-400">
            请先在"实验"标签页中选择一个已完成的实验
          </div>
        )
      )}

      {/* Online Prediction Modal */}
      {showPredictModal && predictRunId && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b">
              <div>
                <h2 className="font-semibold text-gray-900">实时预测排名</h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  模型：<span className="font-mono">{predictRunId.slice(0, 16)}...</span>
                  {predictResult?.date && <span className="ml-2">日期：{predictResult.date}</span>}
                </p>
              </div>
              <button onClick={() => { setShowPredictModal(false); setPredictRunId(null) }}
                className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
            </div>
            <div className="flex-1 overflow-auto p-4">
              {predictFetching ? (
                <div className="flex items-center justify-center py-8 text-gray-500">
                  <div className="animate-spin w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full mr-2" />
                  模型加载中...
                </div>
              ) : predictResult?.predictions?.length ? (
                <>
                  <div className="text-xs text-gray-500 mb-3">
                    共 {predictResult.total_assets} 只资产，展示 Top-{predictResult.top_n}
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 border-b">
                        <th className="py-1.5 pr-3 w-12">#</th>
                        <th className="py-1.5 pr-3">资产代码</th>
                        <th className="py-1.5 text-right">预测收益</th>
                      </tr>
                    </thead>
                    <tbody>
                      {predictResult.predictions.map((p, i) => (
                        <tr key={p.asset_id}
                          className={`border-b border-gray-100 ${i < 3 ? 'bg-green-50' : i >= predictResult.predictions.length - 3 ? 'bg-red-50' : ''}`}>
                          <td className="py-1.5 pr-3 font-mono text-gray-400">{p.rank}</td>
                          <td className="py-1.5 pr-3 font-mono font-medium">{p.asset_id}</td>
                          <td className={`py-1.5 text-right font-mono ${
                            p.prediction > 0 ? 'text-green-600' : p.prediction < 0 ? 'text-red-600' : 'text-gray-400'
                          }`}>
                            {(p.prediction * 100).toFixed(2)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              ) : (
                <div className="text-center text-gray-400 py-8">无预测数据</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

import { useState, useMemo, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { factorAnalyticsApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { FactorCard } from '@/components/factors/FactorCard'
import { ICCalculator } from '@/components/factors/ICCalculator'
import { ICAnalysisTab } from '@/components/factors/ICAnalysisTab'
import { CorrelationTab } from '@/components/factors/CorrelationTab'
import { ICDecayTab } from '@/components/factors/ICDecayTab'
import { QuintileTab } from '@/components/factors/QuintileTab'
import { CreateFactorModal } from '@/components/factors/CreateFactorModal'
import { ICAlertModal } from '@/components/factors/ICAlertModal'
import { useWorkflowStore } from '@/stores/workflowStore'

type TabKey = 'selection' | 'ic' | 'quintile' | 'correlation' | 'decay'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'selection', label: '因子选择' },
  { key: 'ic', label: 'IC 分析' },
  { key: 'quintile', label: '五分位' },
  { key: 'correlation', label: '相关性' },
  { key: 'decay', label: 'IC 衰减' },
]

export function FactorsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<TabKey>('selection')
  const [selectedFactor, setSelectedFactor] = useState<string | null>(null)
  const [featureSetVersion, setFeatureSetVersion] = useState('')
  const [horizonDays, setHorizonDays] = useState(1)
  const [selectedFactors, setSelectedFactors] = useState<string[]>([])
  const [factorSearch, setFactorSearch] = useState('')
  const [showCreateFactor, setShowCreateFactor] = useState(false)
  const [icThreshold, setIcThreshold] = useState(0.02)
  const [alertFactorName, setAlertFactorName] = useState<string | null>(null)

  // Queries
  const { data: defs, isLoading } = useQuery({
    queryKey: extendedQueryKeys.factorAnalytics.definitions(),
    queryFn: factorAnalyticsApi.definitions,
  })

  const { data: versions } = useQuery({
    queryKey: ['factors', 'versions'],
    queryFn: () => factorAnalyticsApi.versions(),
  })

  const { data: icStatus } = useQuery({
    queryKey: ['factors', 'ic-status', featureSetVersion, icThreshold],
    queryFn: () => factorAnalyticsApi.icStatus({
      feature_set_version: featureSetVersion || undefined,
      threshold: icThreshold,
    }),
    staleTime: 60_000,
  })

  const activeJobId = searchParams.get('ic_job')
  const { data: jobResult } = useQuery({
    queryKey: extendedQueryKeys.factorAnalytics.icJob(activeJobId ?? ''),
    queryFn: () => factorAnalyticsApi.icJob(activeJobId!),
    enabled: !!activeJobId,
    refetchInterval: (query) => {
      const d = query.state.data
      return d && (d.status === 'done' || d.status === 'error') ? false : 2000
    },
  })

  const { data: quintileData, isLoading: quintileLoading } = useQuery({
    queryKey: extendedQueryKeys.factorAnalytics.quintiles(selectedFactor!, featureSetVersion, horizonDays),
    queryFn: () => factorAnalyticsApi.computeQuintiles({
      factor_name: selectedFactor!,
      feature_set_version: featureSetVersion,
      horizon_days: horizonDays,
    }),
    enabled: !!selectedFactor && !!featureSetVersion && activeTab === 'quintile',
    staleTime: 60_000,
  })

  const icSummary = jobResult?.status === 'done' ? jobResult.summary_json : undefined

  // Workflow integration: update context when IC job completes
  const { currentWorkflow, updateContext } = useWorkflowStore()
  useEffect(() => {
    if (jobResult?.status === 'done' && currentWorkflow === 'factor-to-backtest' && selectedFactors.length > 0) {
      const icResults: Record<string, number> = {}
      if (icSummary?.mean_ic != null) {
        for (const f of selectedFactors) {
          icResults[f] = icSummary.mean_ic
        }
      }
      updateContext({
        selectedFactors,
        factorICResults: icResults,
      })
    }
  }, [jobResult?.status, currentWorkflow, selectedFactors, icSummary, updateContext])

  // Filtered factors
  const filteredFactorDefs = useMemo(() => {
    if (!defs?.items) return []
    if (!factorSearch.trim()) return defs.items
    const q = factorSearch.toLowerCase()
    return defs.items.filter(
      f => f.name.toLowerCase().includes(q) || (f.description ?? '').toLowerCase().includes(q)
    )
  }, [defs, factorSearch])

  // IC alert factors set
  const icAlertFactors = useMemo(() => {
    const set = new Set<string>()
    if (icStatus?.items) {
      for (const item of icStatus.items) {
        if (item.is_alert) set.add(item.factor_name)
      }
    }
    return set
  }, [icStatus])

  // Remove selected factors that become hidden by search
  useEffect(() => {
    if (!factorSearch.trim()) return
    const visibleNames = new Set(filteredFactorDefs.map(f => f.name))
    setSelectedFactors(prev => prev.filter(n => visibleNames.has(n)))
  }, [filteredFactorDefs, factorSearch])

  return (
    <div>
      <h1 className="page-title">Alpha 因子研究</h1>
      <p className="page-subtitle">浏览内置因子、计算 IC/IR 时间序列</p>

      {/* Feature Set selector */}
      <div className="flex gap-3 mb-4">
        <select className="input max-w-xs" value={featureSetVersion} onChange={e => setFeatureSetVersion(e.target.value)}>
          <option value="">选择 Feature Set 版本</option>
          {versions?.items?.map((v: { feature_set_version: string }) => (
            <option key={v.feature_set_version} value={v.feature_set_version}>
              {v.feature_set_version.slice(0, 16)}...
            </option>
          ))}
        </select>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 border-b">
        {TABS.map(tab => (
          <button key={tab.key}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key ? 'border-blue-600 text-blue-700' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setActiveTab(tab.key)}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab: Factor Selection */}
      {activeTab === 'selection' && (
        <div className="flex gap-6">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-3">
              <div className="relative flex-1">
                <input type="text" placeholder="搜索因子名称或描述..."
                  value={factorSearch} onChange={e => setFactorSearch(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-sm border rounded-lg focus:outline-none focus:ring-1 focus:ring-brand-500" />
                <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-xs">🔍</span>
                {factorSearch && (
                  <button onClick={() => setFactorSearch('')}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs">✕</button>
                )}
              </div>
              <button onClick={() => setShowCreateFactor(true)} className="btn-primary text-xs px-3 py-1.5 flex-shrink-0">
                + 新建因子
              </button>
            </div>
            {factorSearch && (
              <p className="text-xs text-gray-400 mb-2">找到 {filteredFactorDefs.length} / {defs?.items.length ?? 0} 个因子</p>
            )}

            {/* IC Alert Summary */}
            {icStatus && icStatus.items.some(i => i.is_alert) && (
              <div className="flex items-center gap-2 mb-2 px-2 py-1.5 bg-red-50 border border-red-200 rounded text-xs text-red-700">
                <span>{icStatus.items.filter(i => i.is_alert).length} 个因子 IC 低于阈值</span>
                <span className="text-red-400">|</span>
                <span>阈值：</span>
                <input type="number" value={icThreshold} onChange={e => setIcThreshold(Number(e.target.value))}
                  className="w-16 px-1 py-0.5 border border-red-300 rounded text-xs" min={0.001} max={0.1} step={0.005} />
              </div>
            )}

            {isLoading && <p className="text-gray-400">Loading...</p>}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredFactorDefs.map(f => (
                <FactorCard key={f.name} factor={f} selected={selectedFactor === f.name}
                  hasAlert={icAlertFactors.has(f.name)}
                  alertMessage={icStatus?.items.find(i => i.factor_name === f.name)?.alert_message ?? undefined}
                  onClick={() => {
                    const next = selectedFactor === f.name ? null : f.name
                    setSelectedFactor(next)
                    if (next !== selectedFactor) setSearchParams(prev => { prev.delete('ic_job'); return prev }, { replace: true })
                  }}
                  onAlertClick={() => setAlertFactorName(f.name)} />
              ))}
              {filteredFactorDefs.length === 0 && !isLoading && (
                <div className="col-span-full text-center py-8 text-gray-400 text-sm">
                  {factorSearch ? `未找到含"${factorSearch}"的因子` : '暂无因子数据'}
                </div>
              )}
            </div>

            {/* Multi-factor chips */}
            {defs?.items && defs.items.length > 0 && (
              <div className="mt-6">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-medium text-gray-700">多因子选择（用于相关性/IC矩阵）</h3>
                  <button className="text-xs text-blue-600 hover:underline"
                    onClick={() => setSelectedFactors(filteredFactorDefs.map(f => f.name))}>
                    {factorSearch ? `全选 (${filteredFactorDefs.length})` : '全选'}
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {filteredFactorDefs.map(f => (
                    <button key={f.name}
                      className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                        selectedFactors.includes(f.name) ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'
                      }`}
                      onClick={() => setSelectedFactors(prev =>
                        prev.includes(f.name) ? prev.filter(n => n !== f.name) : [...prev, f.name]
                      )}>
                      {f.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="w-72 flex-shrink-0">
            <ICCalculator selectedFactors={selectedFactors} featureSetVersion={featureSetVersion}
              horizonDays={horizonDays} onHorizonChange={setHorizonDays}
              onJobCreated={(jobId) => setSearchParams(prev => { prev.set('matrix_job', jobId); return prev }, { replace: true })} />
          </div>
        </div>
      )}

      {/* Tab: IC Analysis */}
      {activeTab === 'ic' && (
        selectedFactor
          ? <ICAnalysisTab selectedFactor={selectedFactor} featureSetVersion={featureSetVersion} />
          : <div className="card text-center py-8 text-gray-400">请先在"因子选择"标签页中选择一个因子</div>
      )}

      {/* Tab: Quintile */}
      {activeTab === 'quintile' && (
        !selectedFactor
          ? <div className="card text-center py-8 text-gray-400">请先在"因子选择"标签页中选择一个因子</div>
          : !featureSetVersion
            ? <div className="card text-center py-8 text-gray-400">请先选择 Feature Set 版本</div>
            : quintileLoading
              ? <div className="card text-center py-8 text-gray-400">加载中...</div>
              : quintileData?.groups
                ? <QuintileTab quantileReturns={quintileData.groups.map(g => ({ quantile: parseInt(String(g.quintile), 10) || 0, mean_return: g.mean_return }))} />
                : <div className="card text-center py-8 text-gray-400">暂无分位收益数据</div>
      )}

      {/* Tab: Correlation */}
      {activeTab === 'correlation' && (
        <CorrelationTab selectedFactors={selectedFactors} featureSetVersion={featureSetVersion} />
      )}

      {/* Tab: IC Decay */}
      {activeTab === 'decay' && (
        icSummary?.rank_ic_decay
          ? <ICDecayTab rankIcDecay={icSummary.rank_ic_decay} />
          : <div className="card text-center py-8 text-gray-400">请先在"IC 分析"标签页中计算IC，衰减数据将自动生成</div>
      )}

      {/* Modals */}
      {showCreateFactor && <CreateFactorModal onClose={() => setShowCreateFactor(false)} />}
      {alertFactorName && <ICAlertModal factorName={alertFactorName} defaultThreshold={icThreshold} onClose={() => setAlertFactorName(null)} />}
    </div>
  )
}

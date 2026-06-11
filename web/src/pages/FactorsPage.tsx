import { useState, useMemo, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { factorAnalyticsApi, customFactorApi, alertsApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { LineChart, Line, BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'
import { toast } from 'sonner'
import { FactorDSLEditor } from '@/components/factors/FactorDSLEditor'

export function FactorsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const [selectedFactor, setSelectedFactor] = useState<string | null>(null)
  const [featureSetVersion, setFeatureSetVersion] = useState('')
  const [horizonDays, setHorizonDays] = useState(1)

  const activeJobId = searchParams.get('ic_job')
  const matrixJobId = searchParams.get('matrix_job')

  const [selectedFactors, setSelectedFactors] = useState<string[]>([])
  const [sortBy, setSortBy] = useState<'mean_ic' | 'ir' | 'hit_rate'>('mean_ic')

  // Quintile returns
  const [showQuintile, setShowQuintile] = useState(false)
  const { data: quintileData, isFetching: quintileFetching, refetch: refetchQuintile } = useQuery({
    queryKey: ['factors', 'quintile', selectedFactor, featureSetVersion, horizonDays],
    queryFn: () => factorAnalyticsApi.computeQuintiles({
      factor_name: selectedFactor!,
      feature_set_version: featureSetVersion,
      horizon_days: horizonDays,
    }),
    enabled: false,
  })

  // Factor correlation heatmap
  const [showCorrMap, setShowCorrMap] = useState(false)

  const qc = useQueryClient()
  const [showCreateFactor, setShowCreateFactor] = useState(false)
  const [cfName, setCfName] = useState('')
  const [cfExpr, setCfExpr] = useState('')
  const [cfDesc, setCfDesc] = useState('')
  const [exprType, setExprType] = useState<'polars' | 'dsl'>('dsl')
  const [cfPreview, setCfPreview] = useState<{
    valid: boolean
    error: string | null
    preview: { asset_id: string; trade_date: string; value: number | null }[]
  } | null>(null)
  const [cfPreviewLoading, setCfPreviewLoading] = useState(false)

  // IC Alert
  const [icThreshold, setIcThreshold] = useState(0.02)
  const [showIcAlertModal, setShowIcAlertModal] = useState(false)
  const [alertFactorName, setAlertFactorName] = useState<string | null>(null)
  const [alertIcThreshold, setAlertIcThreshold] = useState(0.02)
  const [alertWindowDays, setAlertWindowDays] = useState(20)

  const createAlertMutation = useMutation({
    mutationFn: alertsApi.createRule,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'rules'] })
      toast.success(`已为 ${alertFactorName} 创建 IC 告警规则`)
      setShowIcAlertModal(false)
      setAlertFactorName(null)
    },
    onError: (e: Error) => toast.error(`创建失败: ${e.message}`),
  })

  const { data: icStatus } = useQuery({
    queryKey: ['factors', 'ic-status', featureSetVersion, icThreshold],
    queryFn: () => factorAnalyticsApi.icStatus({
      feature_set_version: featureSetVersion || undefined,
      threshold: icThreshold,
    }),
    staleTime: 60_000,
  })

  // Build a set of factor names that have IC alerts
  const icAlertFactors = useMemo(() => {
    const set = new Set<string>()
    if (icStatus?.items) {
      for (const item of icStatus.items) {
        if (item.is_alert) set.add(item.factor_name)
      }
    }
    return set
  }, [icStatus])

  const createFactorMutation = useMutation({
    mutationFn: customFactorApi.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['factors', 'definitions'] })
      setShowCreateFactor(false)
      setCfName(''); setCfExpr(''); setCfDesc(''); setCfPreview(null); setExprType('dsl')
      toast.success('自定义因子已创建')
    },
    onError: (e: Error) => toast.error(`创建失败: ${e.message}`),
  })

  async function handlePreviewFactor() {
    if (!cfExpr.trim()) return
    setCfPreviewLoading(true)
    try {
      const result = await customFactorApi.preview({ expression: cfExpr })
      setCfPreview(result)
    } catch (e: unknown) {
      setCfPreview({ valid: false, error: String(e), preview: [] })
    } finally {
      setCfPreviewLoading(false)
    }
  }

  const { data: corrMatrix, isFetching: corrFetching, refetch: refetchCorr } = useQuery({
    queryKey: ['factors', 'correlation', selectedFactors, featureSetVersion],
    queryFn: () => factorAnalyticsApi.computeFactorCorrelation({
      factor_names: selectedFactors,
      feature_set_version: featureSetVersion,
    }),
    enabled: false,
  })

  function corrColor(v: number | null): string {
    if (v === null) return '#f3f4f6'
    const abs = Math.abs(v)
    if (v >= 0) return `oklch(${92 - abs * 45}% 0.12 250)`
    return `oklch(${92 - abs * 45}% 0.12 25)`
  }

  const { data: defs, isLoading } = useQuery({
    queryKey: extendedQueryKeys.factorAnalytics.definitions(),
    queryFn: factorAnalyticsApi.definitions,
  })

  const [factorSearch, setFactorSearch] = useState('')

  const filteredFactorDefs = useMemo(() => {
    if (!defs?.items) return []
    if (!factorSearch.trim()) return defs.items
    const q = factorSearch.toLowerCase()
    return defs.items.filter(
      f => f.name.toLowerCase().includes(q) || (f.description ?? '').toLowerCase().includes(q)
    )
  }, [defs, factorSearch])

  // Remove selected factors that are no longer visible after search filter changes
  useEffect(() => {
    if (!factorSearch.trim()) return
    const visibleNames = new Set(filteredFactorDefs.map(f => f.name))
    setSelectedFactors(prev => prev.filter(n => visibleNames.has(n)))
  }, [filteredFactorDefs, factorSearch])

  const { data: versions } = useQuery({
    queryKey: ["factors", "versions"],
    queryFn: () => factorAnalyticsApi.versions(),
  })

  const computeMutation = useMutation({
    mutationFn: (params: { factor_name: string; feature_set_version: string }) =>
      factorAnalyticsApi.computeIC({ ...params, horizon_days: horizonDays }),
    onSuccess: (data) => {
      setSearchParams(prev => { prev.set('ic_job', data.job_id); return prev }, { replace: true })
    },
  })

  const matrixMutation = useMutation({
    mutationFn: () =>
      factorAnalyticsApi.computeICMatrix({
        factor_names: selectedFactors,
        feature_set_version: featureSetVersion,
        horizon_days: horizonDays,
      }),
    onSuccess: (data) => {
      setSearchParams(prev => { prev.set('matrix_job', data.job_id); return prev }, { replace: true })
    },
  })

  const { data: matrixResult } = useQuery({
    queryKey: ['factors', 'matrix', matrixJobId ?? ''],
    queryFn: () => factorAnalyticsApi.icJob(matrixJobId!),
    enabled: !!matrixJobId,
    refetchInterval: (query) => {
      const d = query.state.data
      return d && (d.status === 'done' || d.status === 'error') ? false : 2000
    },
  })

  const { data: jobResult } = useQuery({
    queryKey: extendedQueryKeys.factorAnalytics.icJob(activeJobId ?? ''),
    queryFn: () => factorAnalyticsApi.icJob(activeJobId!),
    enabled: !!activeJobId,
    refetchInterval: (query) => {
      const d = query.state.data
      return d && (d.status === 'done' || d.status === 'error') ? false : 2000
    },
  })

  const icSeries = jobResult?.status === 'done' ? (jobResult.series_json ?? []) : []
  const icSummary = jobResult?.summary_json

  return (
    <div>
      <h1 className="page-title">Alpha 因子研究</h1>
      <p className="page-subtitle">浏览内置因子、计算 IC/IR 时间序列</p>

      {/* 流程步骤提示 */}
      <div className="flex items-center gap-2 mb-5 p-3 bg-blue-50 rounded-lg border border-blue-100">
        {[
          { n: 1, label: '选择 Feature Set 版本', done: !!featureSetVersion },
          { n: 2, label: '选择要分析的因子', done: !!selectedFactor },
          { n: 3, label: '点击"计算 IC 分析"', done: icSeries.length > 0 },
        ].map((step, idx, arr) => (
          <div key={step.n} className="flex items-center gap-2">
            <div className={`flex items-center gap-1.5 text-sm font-medium ${
              step.done ? 'text-green-700' : idx === arr.filter(s => s.done).length ? 'text-blue-700' : 'text-gray-400'
            }`}>
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
                step.done ? 'bg-green-600 text-white' : idx === arr.filter(s => s.done).length ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'
              }`}>
                {step.done ? '✓' : step.n}
              </span>
              {step.label}
            </div>
            {idx < arr.length - 1 && <span className="text-gray-300">→</span>}
          </div>
        ))}
      </div>

      <div className="flex gap-3 mb-6">
        <select
          className="input max-w-xs"
          value={featureSetVersion}
          onChange={e => setFeatureSetVersion(e.target.value)}
        >
          <option value="">选择 Feature Set 版本</option>
          {versions?.items?.map((v: { feature_set_version: string }) => (
            <option key={v.feature_set_version} value={v.feature_set_version}>
              {v.feature_set_version.slice(0, 16)}…
            </option>
          ))}
        </select>
      </div>

      {isLoading && <p className="text-gray-400">Loading…</p>}

      {/* 因子搜索 + 新建按钮 */}
      <div className="flex items-center gap-2 mb-3">
        <div className="relative flex-1">
          <input
            type="text"
            placeholder="搜索因子名称或描述…"
            value={factorSearch}
            onChange={e => setFactorSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-sm border rounded-lg focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-xs">🔍</span>
          {factorSearch && (
            <button
              onClick={() => setFactorSearch('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs"
            >✕</button>
          )}
        </div>
        <button
          onClick={() => setShowCreateFactor(true)}
          className="btn-primary text-xs px-3 py-1.5 flex-shrink-0"
        >
          + 新建因子
        </button>
      </div>
      {factorSearch && (
        <p className="text-xs text-gray-400 mb-2">
          找到 {filteredFactorDefs.length} / {defs?.items.length ?? 0} 个因子
        </p>
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

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {filteredFactorDefs.map(f => (
          <div
            key={f.name}
            onClick={() => {
              const next = selectedFactor === f.name ? null : f.name
              setSelectedFactor(next)
              if (next !== selectedFactor) setSearchParams(prev => { prev.delete('ic_job'); return prev }, { replace: true })
            }}
            className={`card cursor-pointer hover:shadow-md transition-shadow border-2 ${
              selectedFactor === f.name ? 'border-blue-500' : 'border-transparent'
            }`}
          >
            <div className="font-semibold text-gray-900 mb-1">
              {f.name}
              {icAlertFactors.has(f.name) && (
                <button
                  className="ml-1 text-red-500 text-xs"
                  title={icStatus?.items.find(i => i.factor_name === f.name)?.alert_message || 'IC 低于阈值'}
                  aria-label={`${f.name} IC 告警`}
                  onClick={(e) => {
                    e.stopPropagation()
                    setAlertFactorName(f.name)
                    setAlertIcThreshold(icThreshold)
                    setAlertWindowDays(20)
                    setShowIcAlertModal(true)
                  }}
                >
                  ⚠
                </button>
              )}
            </div>
            <div className="text-xs text-gray-500 mb-2">{f.description || '无描述'}</div>
            <div className="flex flex-wrap gap-1">
              {f.tags.map(t => (
                <span key={t} className="badge bg-blue-50 text-blue-700">{t}</span>
              ))}
            </div>
            {f.source === 'custom' && (
              <span className="mt-1 text-xs px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded inline-block">🔧 自定义</span>
            )}
          </div>
        ))}
        {filteredFactorDefs.length === 0 && !isLoading && (
          <div className="col-span-full text-center py-8 text-gray-400 text-sm">
            {factorSearch ? `未找到含"${factorSearch}"的因子` : '暂无因子数据'}
          </div>
        )}
      </div>

      {/* Multi-Factor IC Matrix */}
      {defs?.items && defs.items.length > 0 && (
        <div className="card mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-900">多因子 IC 矩阵</h2>
            <div className="flex items-center gap-3">
              <button
                className="text-xs text-blue-600 hover:underline"
                onClick={() => setSelectedFactors(filteredFactorDefs.map(f => f.name))}
              >
                {factorSearch ? `全选 (${filteredFactorDefs.length})` : '全选'}
              </button>
              <span className="text-xs text-gray-400">选择 ≥2 个因子</span>
              <button
                className="btn-primary text-sm"
                disabled={selectedFactors.length < 2 || !featureSetVersion || matrixMutation.isPending}
                onClick={() => matrixMutation.mutate()}
              >
                {matrixMutation.isPending ? '计算中…' : '计算 IC 矩阵'}
              </button>
              <button
                className="btn-secondary text-sm"
                disabled={selectedFactors.length === 0}
                onClick={() => navigate('/scoring', { state: { selectedFactors } })}
              >
                发送到打分
              </button>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 mb-4">
            {filteredFactorDefs.map(f => (
              <button
                key={f.name}
                className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                  selectedFactors.includes(f.name)
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'
                }`}
                onClick={() => setSelectedFactors(prev =>
                  prev.includes(f.name) ? prev.filter(n => n !== f.name) : [...prev, f.name]
                )}
              >
                {f.name}
              </button>
            ))}
          </div>

          {matrixJobId && matrixResult?.status !== 'done' && matrixResult?.status !== 'error' && (
            <p className="text-blue-500 text-sm">计算中… (job: {matrixJobId.slice(0, 8)})</p>
          )}

          {matrixResult?.status === 'error' && (
            <p className="text-red-500 text-sm">{(matrixResult as unknown as { error_text?: string }).error_text}</p>
          )}

          {matrixResult?.status === 'done' && matrixResult.summary_json && (() => {
            const summary = matrixResult.summary_json as unknown as {
              factors: string[]
              correlation: number[][]
              factor_stats: Record<string, { mean_ic: number; ir: number; hit_rate: number }>
              observations: number
            }
            return (
              <div>
                <div className="text-xs text-gray-400 mb-3">{summary.observations} 个交易日</div>
                {/* Correlation heatmap as table */}
                <div className="overflow-x-auto">
                  <table className="text-xs">
                    <thead>
                      <tr>
                        <th className="px-2 py-1"></th>
                        {summary.factors.map(f => (
                          <th key={f} className="px-2 py-1 font-medium text-gray-600 writing-mode-vertical" style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>{f}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {summary.factors.map((rowFactor, i) => (
                        <tr key={rowFactor}>
                          <td className="px-2 py-1 font-medium text-gray-600 whitespace-nowrap">{rowFactor}</td>
                          {summary.correlation[i].map((val, j) => {
                            const absVal = Math.abs(val)
                            const bg = val >= 0
                              ? `rgba(34, 197, 94, ${absVal * 0.6})`
                              : `rgba(239, 68, 68, ${absVal * 0.6})`
                            return (
                              <td key={j} className="px-2 py-1 text-center font-mono" style={{ backgroundColor: bg }}>
                                {val.toFixed(2)}
                              </td>
                            )
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Factor ranking table */}
                <div className="mt-4">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-medium text-gray-700">因子排名</h3>
                    <div className="flex gap-1">
                      {(['mean_ic', 'ir', 'hit_rate'] as const).map(key => (
                        <button
                          key={key}
                          className={`px-2 py-0.5 text-xs rounded ${sortBy === key ? 'bg-blue-100 text-blue-700' : 'text-gray-400 hover:text-gray-600'}`}
                          onClick={() => setSortBy(key)}
                        >
                          {key === 'mean_ic' ? 'Mean IC' : key === 'ir' ? 'IR' : 'Hit Rate'}
                        </button>
                      ))}
                    </div>
                  </div>
                  <table className="w-full text-xs">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="table-th w-8">#</th>
                        <th className="table-th">因子</th>
                        <th className="table-th">Mean IC</th>
                        <th className="table-th">IR</th>
                        <th className="table-th">Hit Rate</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(summary.factor_stats)
                        .sort(([, a], [, b]) => Math.abs(b[sortBy]) - Math.abs(a[sortBy]))
                        .map(([fn, stats], idx) => (
                          <tr key={fn} className="table-row">
                            <td className="table-td text-gray-400">{idx + 1}</td>
                            <td className="table-td font-medium">{fn}</td>
                            <td className={`table-td font-mono ${Math.abs(stats.mean_ic) > 0.03 ? 'text-green-700 font-bold' : ''}`}>{stats.mean_ic.toFixed(4)}</td>
                            <td className={`table-td font-mono ${Math.abs(stats.ir) > 0.5 ? 'text-green-700 font-bold' : ''}`}>{stats.ir.toFixed(4)}</td>
                            <td className="table-td font-mono">{(stats.hit_rate * 100).toFixed(1)}%</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )
          })()}

          {/* Factor Correlation Heatmap */}
          {selectedFactors.length >= 2 && (
            <div className="card mt-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-800">因子相关性矩阵</h3>
                {!showCorrMap ? (
                  <button className="btn-secondary text-xs" onClick={() => { setShowCorrMap(true); refetchCorr() }}>
                    计算相关性
                  </button>
                ) : corrFetching ? (
                  <span className="text-xs text-gray-400">计算中…</span>
                ) : null}
              </div>
              {corrMatrix && corrMatrix.factors.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="text-xs border-collapse mx-auto">
                    <thead>
                      <tr>
                        <th className="w-20" />
                        {corrMatrix.factors.map(f => (
                          <th key={f} className="p-1 text-center font-mono w-14 max-w-[56px] truncate" title={f}>
                            {f.length > 7 ? f.slice(0, 7) + '…' : f}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {corrMatrix.factors.map(f1 => (
                        <tr key={f1}>
                          <td className="p-1 font-mono text-right pr-2 text-gray-600 max-w-[80px] truncate" title={f1}>
                            {f1.length > 9 ? f1.slice(0, 9) + '…' : f1}
                          </td>
                          {corrMatrix.factors.map(f2 => {
                            const cell = corrMatrix.matrix.find(c => c.factor_a === f1 && c.factor_b === f2)
                            const v = cell?.correlation ?? null
                            return (
                              <td
                                key={f2}
                                style={{ background: corrColor(v), width: 52, height: 44 }}
                                className="text-center border border-white/50 font-mono"
                                title={`${f1} × ${f2}: ${v !== null ? v.toFixed(3) : 'N/A'}`}
                              >
                                {v !== null ? v.toFixed(2) : '—'}
                              </td>
                            )
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="text-xs text-gray-400 mt-2 text-center">
                    蓝色 = 正相关，橙红 = 负相关，颜色越深相关度越高
                  </p>
                  <div className="flex justify-center mt-2">
                    <button
                      className="btn-secondary text-xs"
                      onClick={() => {
                        if (!corrMatrix) return
                        const header = ['', ...corrMatrix.factors].join(',')
                        const rows = corrMatrix.factors.map(f1 => {
                          const vals = corrMatrix.factors.map(f2 => {
                            const cell = corrMatrix.matrix.find(c => c.factor_a === f1 && c.factor_b === f2)
                            return cell?.correlation?.toFixed(4) ?? ''
                          })
                          return [f1, ...vals].join(',')
                        })
                        const csv = [header, ...rows].join('\n')
                        const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
                        const url = URL.createObjectURL(blob)
                        const a = document.createElement('a')
                        a.href = url
                        a.download = `factor_correlation_${new Date().toISOString().slice(0, 10)}.csv`
                        a.click()
                        URL.revokeObjectURL(url)
                        toast.success('相关性矩阵已下载')
                      }}
                    >
                      下载 CSV
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {selectedFactor && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">IC 分析：{selectedFactor}</h2>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-500">Horizon</label>
                <select
                  className="input w-28"
                  value={horizonDays}
                  onChange={e => setHorizonDays(Number(e.target.value))}
                >
                  {[1, 2, 3, 5, 10, 20].map(d => (
                    <option key={d} value={d}>{d} 天</option>
                  ))}
                </select>
              </div>
              <button
                onClick={() => computeMutation.mutate({ factor_name: selectedFactor, feature_set_version: featureSetVersion })}
                disabled={!featureSetVersion || computeMutation.isPending}
                className="btn-primary text-sm"
              >
                {computeMutation.isPending ? '提交中…' : '计算 IC/IR'}
              </button>
            </div>
          </div>

          {activeJobId && jobResult?.status !== 'done' && (
            <p className="text-blue-500 text-sm">计算中… (job: {activeJobId.slice(0, 8)})</p>
          )}

          {jobResult?.status === 'error' && (
            <p className="text-red-500 text-sm">计算失败：{(jobResult as unknown as { error_text?: string }).error_text}</p>
          )}

          {icSummary && (
            <div className="grid grid-cols-3 gap-4 mb-4">
              {[
                { label: '平均 IC', value: icSummary.mean_ic?.toFixed(4) },
                { label: 'IR', value: icSummary.ir?.toFixed(4) },
                { label: '正 IC 占比', value: `${((icSummary.hit_rate ?? 0) * 100).toFixed(1)}%` },
              ].map(({ label, value }) => (
                <div key={label} className="text-center p-3 bg-gray-50 rounded-lg">
                  <div className="text-lg font-bold text-brand-600">{value ?? '—'}</div>
                  <div className="text-xs text-gray-500">{label}</div>
                </div>
              ))}
            </div>
          )}

          {icSeries.length > 0 && (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={icSeries}>
                <XAxis dataKey="trade_date" tick={{ fontSize: 10 }} />
                <YAxis domain={[-0.3, 0.3]} tick={{ fontSize: 10 }} />
                <Tooltip />
                <ReferenceLine y={0} stroke="#e5e7eb" />
                <Line type="monotone" dataKey="ic" stroke="#4f63d2" dot={false} strokeWidth={1.5} />
              </LineChart>
            </ResponsiveContainer>
          )}

          {icSummary?.rank_ic_decay && icSummary.rank_ic_decay.length > 0 && (
            <div className="card mt-4">
              <h3 className="font-semibold text-gray-800 mb-3 text-sm">Rank IC 衰减（lag 1-10）</h3>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={icSummary.rank_ic_decay} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                  <XAxis dataKey="lag" tick={{ fontSize: 11 }} label={{ value: 'Lag', position: 'insideRight', fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: unknown) => (v as number).toFixed(4)} />
                  <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
                  <Line type="monotone" dataKey="ic" stroke="#3b82f6" dot={{ r: 3 }} strokeWidth={2} name="IC" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {icSummary?.quantile_returns && icSummary.quantile_returns.length > 0 && (
            <div className="card mt-4">
              <h3 className="font-semibold text-gray-800 mb-3 text-sm">分层收益图（5 分组）</h3>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={icSummary.quantile_returns} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                  <XAxis dataKey="quantile" tick={{ fontSize: 11 }} tickFormatter={(v: number) => `Q${v}`} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                  <Tooltip formatter={(v: unknown) => `${((v as number) * 100).toFixed(3)}%`} />
                  <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
                  <Bar dataKey="mean_return" name="平均收益" radius={[3, 3, 0, 0]}>
                    {icSummary.quantile_returns.map((entry) => (
                      <Cell key={entry.quantile} fill={entry.mean_return >= 0 ? '#22c55e' : '#ef4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {icSummary?.factor_turnover != null && (
            <div className="card mt-4">
              <div className="text-sm text-gray-500 mb-1">因子换手率（Top 20%）</div>
              <div className="text-2xl font-bold text-gray-900">
                {(icSummary.factor_turnover * 100).toFixed(1)}%
              </div>
              <div className="text-xs text-gray-400 mt-1">平均每日顶部资产替换比例</div>
            </div>
          )}

          {/* Quintile Returns */}
          {icSummary && (
            <div className="card mt-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-800">
                  分层收益（{horizonDays}日，{quintileData?.n_groups ?? 5} 分位）
                </h3>
                {!showQuintile ? (
                  <button className="btn-secondary text-xs" onClick={() => { setShowQuintile(true); refetchQuintile() }}>
                    计算分位收益
                  </button>
                ) : quintileFetching ? (
                  <span className="text-xs text-gray-400">计算中…</span>
                ) : null}
              </div>
              {quintileData && quintileData.groups.length > 0 && (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={quintileData.groups} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}>
                    <XAxis dataKey="quintile" tickFormatter={v => `Q${v}`} tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={v => `${(v * 100).toFixed(1)}%`} tick={{ fontSize: 11 }} />
                    <Tooltip
                      formatter={(v: number) => [`${(v * 100).toFixed(3)}%`, '均值收益']}
                      labelFormatter={v => `第 ${v} 分位`}
                    />
                    <Bar dataKey="mean_return" radius={[4, 4, 0, 0]}>
                      {quintileData.groups.map((g, i) => (
                        <Cell
                          key={i}
                          fill={Number(g.quintile) > Math.ceil(quintileData.n_groups / 2)
                            ? `oklch(${50 + i * 4}% 0.18 145)`
                            : `oklch(${60 - i * 4}% 0.18 25)`}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          )}
        </div>
      )}

      {/* 新建自定义因子弹窗 */}
      {showCreateFactor && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className={`bg-white rounded-xl shadow-xl w-full ${exprType === 'dsl' ? 'max-w-4xl' : 'max-w-2xl'}`}>
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="font-semibold text-gray-900">新建自定义因子</h2>
              <button onClick={() => setShowCreateFactor(false)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>

            <div className="p-4 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-600 mb-1">因子名称 <span className="text-red-500">*</span></label>
                  <input value={cfName} onChange={e => setCfName(e.target.value)}
                    placeholder="如 my_momentum_5d" className="input w-full text-sm" />
                  <p className="text-xs text-gray-400 mt-0.5">只允许字母、数字、下划线，不能以数字开头</p>
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">描述（可选）</label>
                  <input value={cfDesc} onChange={e => setCfDesc(e.target.value)}
                    placeholder="如：5日价格变动率" className="input w-full text-sm" />
                </div>
              </div>

              {/* Expression type toggle */}
              <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5 w-fit">
                {(['dsl', 'polars'] as const).map(t => (
                  <button
                    key={t}
                    className={`px-3 py-1 text-xs rounded-md transition-colors ${
                      exprType === t ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                    }`}
                    onClick={() => setExprType(t)}
                  >
                    {t === 'dsl' ? 'DSL 表达式' : 'Python/Polars'}
                  </button>
                ))}
              </div>

              {exprType === 'dsl' ? (
                <FactorDSLEditor
                  onSave={(expression, dslName) => {
                    setCfExpr(expression)
                    if (dslName && !cfName) setCfName(dslName)
                    createFactorMutation.mutate({
                      name: cfName || dslName || 'dsl_factor',
                      expression,
                      description: cfDesc,
                      expression_type: 'dsl',
                    })
                  }}
                  initialExpression={cfExpr}
                />
              ) : (
                <>
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">
                      Python/Polars 表达式 <span className="text-red-500">*</span>
                    </label>
                    <textarea
                      rows={4}
                      value={cfExpr}
                      onChange={e => { setCfExpr(e.target.value); setCfPreview(null) }}
                      placeholder={"示例：\n(close - ma('close', 20)) / std('close', 20)\nroc('close', 5)\nma('volume', 5) / ma('volume', 20) - 1"}
                      className="w-full font-mono text-sm border rounded p-2 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    />
                    <p className="text-xs text-gray-400 mt-1">
                      可用列：close, open, high, low, volume, amount &nbsp;|&nbsp;
                      可用函数：ma(col, n), std(col, n), shift(col, n), roc(col, n), rank(col), log(col), sign(col)
                    </p>
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={handlePreviewFactor}
                        disabled={cfPreviewLoading || !cfExpr.trim()}
                        className="btn-secondary text-xs disabled:opacity-40"
                      >
                        {cfPreviewLoading ? '计算中…' : '▶ 预览计算结果'}
                      </button>
                      {cfPreview && (
                        <span className={`text-xs ${cfPreview.valid ? 'text-green-600' : 'text-red-500'}`}>
                          {cfPreview.valid ? '✓ 表达式有效' : `✗ ${cfPreview.error}`}
                        </span>
                      )}
                    </div>
                    {cfPreview?.valid && cfPreview.preview.length > 0 && (
                      <div className="mt-2 overflow-auto max-h-32">
                        <table className="text-xs w-full">
                          <thead><tr className="text-gray-400">
                            <th className="text-left py-1 pr-3">资产</th>
                            <th className="text-left py-1 pr-3">日期</th>
                            <th className="text-right py-1">因子值</th>
                          </tr></thead>
                          <tbody>
                            {cfPreview.preview.map((row, i) => (
                              <tr key={i} className="border-t">
                                <td className="py-0.5 pr-3 font-mono">{row.asset_id}</td>
                                <td className="py-0.5 pr-3 text-gray-500">{row.trade_date}</td>
                                <td className="py-0.5 text-right font-mono">
                                  {row.value != null ? row.value.toFixed(5) : '—'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>

            <div className="flex justify-end gap-2 p-4 border-t">
              <button onClick={() => setShowCreateFactor(false)} className="btn-secondary text-sm">取消</button>
              {exprType === 'polars' && (
                <button
                  onClick={() => createFactorMutation.mutate({ name: cfName, expression: cfExpr, description: cfDesc })}
                  disabled={!cfName.trim() || !cfExpr.trim() || createFactorMutation.isPending || cfPreview?.valid === false}
                  className="btn-primary text-sm disabled:opacity-40"
                >
                  {createFactorMutation.isPending ? '创建中…' : '创建因子'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* IC Alert Create Modal */}
      {showIcAlertModal && alertFactorName && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm">
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="font-semibold text-gray-900">创建 IC 告警规则</h2>
              <button onClick={() => { setShowIcAlertModal(false); setAlertFactorName(null) }}
                className="text-gray-400 hover:text-gray-700 text-2xl leading-none">&times;</button>
            </div>
            <div className="p-4 space-y-3">
              <div>
                <label className="block text-xs text-gray-600 mb-1">因子</label>
                <div className="font-mono text-sm bg-gray-50 px-2 py-1.5 rounded">{alertFactorName}</div>
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">IC 阈值（绝对值低于此值触发）</label>
                <input type="number" value={alertIcThreshold} onChange={e => setAlertIcThreshold(Number(e.target.value))}
                  className="input w-full" min={0.001} max={0.1} step={0.005} />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">检查窗口（天）</label>
                <input type="number" value={alertWindowDays} onChange={e => setAlertWindowDays(Number(e.target.value))}
                  className="input w-full" min={5} max={120} step={5} />
              </div>
            </div>
            <div className="flex justify-end gap-2 p-4 border-t">
              <button onClick={() => { setShowIcAlertModal(false); setAlertFactorName(null) }}
                className="btn-secondary text-sm">取消</button>
              <button
                disabled={createAlertMutation.isPending}
                onClick={() => createAlertMutation.mutate({
                  rule_type: 'factor_ic_low',
                  params: { factor_name: alertFactorName, threshold: alertIcThreshold, window_days: alertWindowDays },
                })}
                className="btn-primary text-sm disabled:opacity-50"
              >
                {createAlertMutation.isPending ? '创建中...' : '创建告警'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

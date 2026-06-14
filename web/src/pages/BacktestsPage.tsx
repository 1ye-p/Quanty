import { useState, useMemo, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { backtestsApi, backtestExtApi, liveApi, jobsApi } from '@/lib/api'
import { DataTable } from '@/components/ui/DataTable'
import { queryKeys } from '@/lib/queryKeys'
import { toast } from 'sonner'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { PnLChart, type PnLDataPoint } from '@/components/charts/PnLChart'
import { ModelCompareTab } from '@/components/ModelCompareTab'
import { FeatureImportanceTab } from '@/components/FeatureImportanceTab'
import { ModelDiagnosticsTab } from '@/components/ModelDiagnosticsTab'
import {
  BarChart, Bar, LineChart, Line, Legend,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
  Cell, ReferenceLine, CartesianGrid, AreaChart, Area,
  PieChart, Pie
} from 'recharts'

function marketLabel(m?: string) {
  return { CN: 'A股', US: '美股', HK: '港股' }[m ?? 'CN'] ?? 'A股'
}
function adjLabel(a?: string) {
  return { forward: '前复权', backward: '后复权', none: '不复权' }[a ?? 'forward'] ?? '前复权'
}
function rebalanceLabel(r?: string) {
  return { '1d': '每日', '5d': '每周', '20d': '每月' }[r ?? '1d'] ?? r ?? '每日'
}

import { downloadJson, downloadCsv } from '@/lib/download'
import { MetricCard } from '@/components/ui/MetricCard'

type Tab = 'overview' | 'tearsheet' | 'overfitting' | 'fills' | 'walkforward' | 'tca' | 'attribution' | 'risk' | 'advanced' | 'model_compare' | 'feature_importance' | 'model_diagnostics'

function FoldMetricsCard({ folds }: { folds: Record<string, unknown>[] }) {
  if (!folds || folds.length === 0) return null
  return (
    <div className="card">
      <h3 className="font-semibold text-gray-800 mb-3">Walk-Forward Fold 指标</h3>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {folds.map((fold, i) => {
          const metrics = fold.metrics_json as Record<string, number> | null
          const sharpe = metrics?.sharpe ?? 0
          const ret = metrics?.total_return ?? 0
          return (
            <div key={i} className={`text-center p-3 rounded-lg ${sharpe > 0 ? 'bg-green-50' : 'bg-red-50'}`}>
              <div className="text-xs text-gray-500 mb-1">Fold {i + 1}</div>
              <div className={`text-lg font-bold ${sharpe > 0 ? 'text-green-700' : 'text-red-700'}`}>
                {sharpe.toFixed(2)}
              </div>
              <div className="text-xs text-gray-400">Sharpe</div>
              <div className={`text-sm mt-1 ${ret > 0 ? 'text-green-600' : 'text-red-600'}`}>
                {(ret * 100).toFixed(1)}%
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function OverfitScore({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = score > 0.7 ? 'bg-red-500' : score > 0.4 ? 'bg-yellow-500' : 'bg-green-500'
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">过拟合评分</span>
        <span className={`badge ${score > 0.7 ? 'bg-red-100 text-red-800' : score > 0.4 ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'}`}>
          {pct}%
        </span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <div className="text-xs text-gray-400 mt-1">
        {score > 0.7 ? '⚠️ 显著过拟合迹象' : score > 0.4 ? '⚠️ 轻度过拟合' : '✅ 过拟合风险低'}
      </div>
    </div>
  )
}

function mergeNavSeries(
  runs: Array<{ run_id: string; nav_series: { date: string; nav: number }[] }>
): Array<Record<string, unknown>> {
  const dateMap = new Map<string, Record<string, unknown>>()
  runs.forEach(r => {
    r.nav_series.forEach(({ date, nav }) => {
      if (!dateMap.has(date)) dateMap.set(date, { date })
      dateMap.get(date)![r.run_id] = nav
    })
  })
  return Array.from(dateMap.values()).sort((a, b) =>
    String(a['date']).localeCompare(String(b['date']))
  )
}

export function BacktestsPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const initialRunId = searchParams.get('run_id')

  const [selectedId, setSelectedId] = useState<string | null>(initialRunId)
  const [tab, setTab] = useState<Tab>('overview')
  const [confirmAction, setConfirmAction] = useState<{ type: 'cancel' | 'delete'; runId: string } | null>(null)
  const [page, setPage] = useState(0)
  const pageSize = 20
  const [fillsPage, setFillsPage] = useState(0)
  const fillsPageSize = 50
  const [compareIds, setCompareIds] = useState<string[]>([])
  const [showCompare, setShowCompare] = useState(false)
  const [btSearch, setBtSearch] = useState('')
  const [riskWindow, setRiskWindow] = useState(60)

  const qc = useQueryClient()
  const [showDeployWizard, setShowDeployWizard] = useState(false)
  const [deployStep, setDeployStep] = useState(1)
  const [deployCash, setDeployCash] = useState('1000000')
  const [deployRiskMode, setDeployRiskMode] = useState<'conservative' | 'moderate' | 'aggressive'>('conservative')
  const [deployChecklist, setDeployChecklist] = useState({
    confirmBacktest: false,
    understandPaper: false,
    reviewRisk: false,
  })

  const deployMutation = useMutation({
    mutationFn: liveApi.deploy,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['live', 'deployed'] })
      setShowDeployWizard(false)
      setDeployStep(1)
      setDeployChecklist({ confirmBacktest: false, understandPaper: false, reviewRisk: false })
      toast.success('策略已部署为模拟实盘，前往"实盘监控"查看')
    },
    onError: (e: Error) => toast.error(`部署失败: ${e.message}`),
  })

  const cancelMutation = useMutation({
    mutationFn: (runId: string) => jobsApi.cancel(runId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['backtests'] }),
    onError: (e: Error) => toast.error(`取消失败: ${e.message}`),
  })

  const deleteMutation = useMutation({
    mutationFn: (runId: string) => jobsApi.delete(runId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['backtests'] }),
    onError: (e: Error) => toast.error(`删除失败: ${e.message}`),
  })

  const { data, isLoading, isFetching } = useQuery({
    queryKey: queryKeys.backtests.list(page * pageSize, pageSize),
    queryFn: () => backtestsApi.list(page * pageSize, pageSize),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      const d = query.state.data
      return d && !d.items.some(r => r.status === 'running' || r.status === 'pending') ? false : 5000
    },
  })

  const { data: detail } = useQuery({
    queryKey: queryKeys.backtests.detail(selectedId!),
    queryFn: () => backtestsApi.get(selectedId!),
    enabled: !!selectedId,
  })

  const { data: tearsheet } = useQuery({
    queryKey: queryKeys.backtests.tearsheet(selectedId!),
    queryFn: () => backtestExtApi.tearsheet(selectedId!),
    enabled: !!selectedId && tab === 'tearsheet',
  })

  const { data: validationData } = useQuery({
    queryKey: queryKeys.backtests.validationWindows(selectedId!),
    queryFn: () => backtestExtApi.validationWindows(selectedId!),
    enabled: !!selectedId && tab === 'overfitting',
  })

  const { data: multipleTestData } = useQuery({
    queryKey: queryKeys.backtests.multipleTesting(selectedId!),
    queryFn: () => backtestExtApi.multipleTesting(selectedId!),
    enabled: !!selectedId && tab === 'overfitting',
  })

  const { data: analysisData } = useQuery({
    queryKey: queryKeys.backtests.analysis(selectedId!),
    queryFn: () => backtestsApi.getAnalysis(selectedId!),
    enabled: !!selectedId,
    staleTime: 60_000,
    retry: false,  // 404 expected if auto-analysis hasn't completed yet
  })

  const { data: fillsData } = useQuery({
    queryKey: queryKeys.backtests.fills(selectedId!, fillsPage * fillsPageSize, fillsPageSize),
    queryFn: () => backtestsApi.getFills(selectedId!, fillsPage * fillsPageSize, fillsPageSize),
    enabled: !!selectedId && tab === 'fills',
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  })

  const { data: wfData } = useQuery({
    queryKey: queryKeys.backtests.walkForward(selectedId!),
    queryFn: () => backtestsApi.getWalkForwardFolds(selectedId!),
    enabled: !!selectedId && tab === 'walkforward',
    staleTime: 60_000,
  })

  const { data: riskData } = useQuery({
    queryKey: queryKeys.backtests.risk(selectedId!),
    queryFn: () => backtestsApi.getRisk(selectedId!, 20),
    enabled: !!selectedId && tab === 'overview',
    staleTime: 60_000,
  })

  const { data: tcaData } = useQuery({
    queryKey: queryKeys.backtests.tca(selectedId!),
    queryFn: () => backtestsApi.getTca(selectedId!),
    enabled: !!selectedId && tab === 'tca',
  })

  const { data: attributionData } = useQuery({
    queryKey: queryKeys.backtests.attribution(selectedId!),
    queryFn: () => backtestsApi.getAttribution(selectedId!),
    enabled: !!selectedId && tab === 'attribution',
  })

  const { data: riskRollingData } = useQuery({
    queryKey: queryKeys.backtests.riskRolling(selectedId!, riskWindow),
    queryFn: () => backtestsApi.getRiskRolling(selectedId!, riskWindow),
    enabled: !!selectedId && tab === 'risk',
  })

  const { data: drawdownsData } = useQuery({
    queryKey: queryKeys.backtests.drawdowns(selectedId!),
    queryFn: () => backtestsApi.getDrawdowns(selectedId!),
    enabled: !!selectedId && tab === 'risk',
  })

  const { data: drawdownTsData } = useQuery({
    queryKey: queryKeys.backtests.drawdownTimeseries(selectedId!),
    queryFn: () => backtestsApi.getDrawdownTimeseries(selectedId!),
    enabled: !!selectedId && tab === 'risk',
  })

  const { data: returnDistData } = useQuery({
    queryKey: queryKeys.backtests.returnDistribution(selectedId!),
    queryFn: () => backtestsApi.getReturnDistribution(selectedId!),
    enabled: !!selectedId && tab === 'risk',
  })

  const { data: correlationData } = useQuery({
    queryKey: queryKeys.backtests.correlation(selectedId!),
    queryFn: () => backtestsApi.getCorrelation(selectedId!),
    enabled: !!selectedId && tab === 'risk',
  })

  const { data: factorExposureData } = useQuery({
    queryKey: queryKeys.backtests.factorExposure(selectedId!),
    queryFn: () => backtestsApi.getFactorExposure(selectedId!),
    enabled: !!selectedId && tab === 'risk',
  })

  const { data: stressTestData } = useQuery({
    queryKey: queryKeys.backtests.stressTest(selectedId!),
    queryFn: () => backtestsApi.getStressTest(selectedId!),
    enabled: !!selectedId && tab === 'risk',
  })

  const { data: riskContribData } = useQuery({
    queryKey: queryKeys.backtests.riskContribution(selectedId!),
    queryFn: () => backtestsApi.getRiskContribution(selectedId!),
    enabled: !!selectedId && tab === 'risk',
  })

  const { data: calendarAnalysisData } = useQuery({
    queryKey: ['backtests', 'calendar-analysis', selectedId!],
    queryFn: () => backtestsApi.getCalendarAnalysis(selectedId!),
    enabled: !!selectedId && tab === 'advanced',
    staleTime: 120_000,
  })

  const { data: tradeAnalysisData } = useQuery({
    queryKey: ['backtests', 'trade-analysis', selectedId!],
    queryFn: () => backtestsApi.getTradeAnalysis(selectedId!),
    enabled: !!selectedId && tab === 'advanced',
    staleTime: 120_000,
  })

  const { data: compareData, isLoading: compareLoading } = useQuery({
    queryKey: ['backtests', 'compare', compareIds.join(',')],
    queryFn: () => backtestsApi.compare(compareIds.join(',')),
    enabled: showCompare && compareIds.length >= 2,
    staleTime: 60_000,
  })

  // Snapshots from tearsheet
  const snapshots = (tearsheet as Record<string, unknown>)?.snapshots as Record<string, unknown>[] ?? []

  const pnlData: PnLDataPoint[] = snapshots.length > 0
    ? (() => {
        let peak = 0
        return snapshots.map(s => {
          const nav = Number(s.nav ?? 1)
          peak = Math.max(peak, nav)
          return {
            time: String(s.trade_date ?? '').slice(0, 10),
            nav,
            drawdown: peak > 0 ? (nav - peak) / peak : 0,
          }
        })
      })()
    : []

  // Benchmark combined NAV for tearsheet overlay
  const benchmarkNav = ((tearsheet as Record<string, unknown>)?.benchmark_nav ?? []) as { date: string; nav: number }[]
  const benchmarkAssetId = String((tearsheet as Record<string, unknown>)?.benchmark_asset_id ?? '')
  const combinedNav = useMemo(() => {
    if (!snapshots.length) return []
    const bmMap = new Map(benchmarkNav.map(b => [b.date, b.nav]))
    return snapshots.map(s => ({
      date: String(s.trade_date ?? '').slice(0, 10),
      portfolio: Number(s.nav ?? 1),
      benchmark: bmMap.get(String(s.trade_date ?? '').slice(0, 10)) ?? null,
    }))
  }, [snapshots, benchmarkNav])

  const filteredBacktests = useMemo(() => {
    if (!data?.items) return []
    if (!btSearch.trim()) return data.items
    const q = btSearch.toLowerCase()
    return data.items.filter(
      r => r.strategy_id.toLowerCase().includes(q)
        || r.run_id.toLowerCase().includes(q)
        || (r.engine ?? '').toLowerCase().includes(q)
    )
  }, [data, btSearch])

  // Reset fills page when selected backtest changes
  useEffect(() => {
    setFillsPage(0)
  }, [selectedId])

  // Fix 1: Clear selectedId when the selected backtest is filtered out
  useEffect(() => {
    if (selectedId && btSearch && !filteredBacktests.some(r => r.run_id === selectedId)) {
      setSelectedId(null)
    }
  }, [btSearch, filteredBacktests, selectedId])

  // Walk-forward windows for chart
  const wfWindows = validationData?.walk_forward ?? []
  const cpvcWindows = validationData?.cpcv ?? []

  const wfChartData = wfWindows.map((w: Record<string, unknown>, i: number) => ({
    window: `W${i + 1}`,
    sharpe: Number((w.metrics_json as Record<string, number> | null)?.sharpe ?? 0),
  }))

  const analysis = analysisData as Record<string, unknown> | null | undefined
  const overfitScore = Number(analysis?.overall_overfit_score ?? 0)
  const psr = Number(analysis?.psr ?? 0)
  const dsr = Number(analysis?.dsr ?? 0)

  const isWalkForward = detail?.engine === 'walk_forward'

  const TABS: { id: Tab; label: string }[] = [
    { id: 'overview', label: '概览' },
    { id: 'tearsheet', label: 'Tearsheet' },
    { id: 'overfitting', label: '过拟合分析' },
    { id: 'fills', label: '交易明细' },
    ...(isWalkForward ? [{ id: 'walkforward' as Tab, label: 'Walk-Forward' }] : []),
    { id: 'tca', label: '成本分析' },
    { id: 'attribution', label: '归因分析' },
    { id: 'risk', label: '风险分析' },
    { id: 'advanced', label: '高级分析' },
    { id: 'model_compare', label: '模型对比' },
    { id: 'feature_importance', label: '特征重要性' },
    { id: 'model_diagnostics', label: '模型诊断' },
  ]

  return (
    <div>
      <h1 className="page-title">回测评估</h1>
      <div className="flex items-center justify-between mb-1">
        <p className="page-subtitle">
          {btSearch
            ? `找到 ${filteredBacktests.length} / ${data?.items?.length ?? 0} 条（当前页）· 共 ${data?.total ?? 0} 条`
            : `共 ${data?.total ?? 0} 条记录 · 点击行选择查看详情`}
        </p>
        <div className="relative">
          <input
            type="text"
            placeholder="搜索策略名或 run_id…"
            value={btSearch}
            onChange={e => setBtSearch(e.target.value)}
            className="pl-6 pr-6 py-1 text-xs border rounded focus:outline-none focus:ring-1 focus:ring-brand-500 w-44"
          />
          <span className="absolute left-1.5 top-1/2 -translate-y-1/2 text-gray-400 text-xs">🔍</span>
          {btSearch && (
            <button onClick={() => setBtSearch('')}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs">✕</button>
          )}
        </div>
      </div>

      {/* Run list */}
      <div className="card p-0 overflow-hidden mb-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-600" />
            <span className="ml-2 text-sm text-gray-500">加载中…</span>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="table-th w-10"><span className="sr-only">选择</span></th>
                {['Run ID', '策略', '引擎', '状态', '开始', '结束', '操作'].map(h => (
                  <th key={h} className="table-th">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {!filteredBacktests.length && (
                <tr><td colSpan={8} className="table-td text-center text-gray-400 py-8">
                  {isFetching ? '加载中…' : btSearch ? '未找到匹配的回测记录' : '暂无回测记录'}
                </td></tr>
              )}
              {filteredBacktests.map(r => (
                <tr
                  key={r.run_id}
                  className={`table-row ${r.is_running_job ? 'opacity-60' : 'cursor-pointer'} ${selectedId === r.run_id ? 'bg-blue-50' : ''}`}
                  onClick={r.is_running_job ? undefined : () => { setSelectedId(r.run_id); setTab('overview') }}
                >
                  <td className="table-td" onClick={e => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      disabled={!!r.is_running_job}
                      checked={compareIds.includes(r.run_id)}
                      onChange={e =>
                        setCompareIds(prev =>
                          e.target.checked
                            ? [...prev.slice(0, 5), r.run_id]
                            : prev.filter(id => id !== r.run_id)
                        )
                      }
                      className="w-4 h-4 rounded border-gray-300 accent-brand-600 disabled:opacity-40"
                    />
                  </td>
                  <td className="table-td font-mono text-xs">{r.is_running_job ? '—' : `${r.run_id.slice(0, 8)}…`}</td>
                  <td className="table-td font-medium">{r.is_running_job ? <span className="text-blue-600">任务提交中…</span> : r.strategy_id}</td>
                  <td className="table-td text-gray-500">
                    {r.is_running_job
                      ? '—'
                      : r.engine === 'walk_forward'
                        ? <span className="px-1.5 py-0.5 text-xs rounded bg-purple-100 text-purple-700 font-medium">WF 汇总</span>
                        : <span className="text-gray-500">{r.engine}</span>}
                  </td>
                  <td className="table-td"><StatusBadge status={r.status} /></td>
                  <td className="table-td text-gray-400">{r.started_at?.slice(0, 16) ?? '—'}</td>
                  <td className="table-td text-gray-400">{r.completed_at?.slice(0, 16) ?? '—'}</td>
                  <td className="table-td" onClick={e => e.stopPropagation()}>
                    {(r.status === 'running' || r.status === 'pending') && (
                      <button
                        onClick={() => setConfirmAction({ type: 'cancel', runId: r.run_id })}
                        className="text-red-500 hover:text-red-700 mr-2 text-xs"
                        title="停止"
                      >&#9209;</button>
                    )}
                    <button
                      onClick={() => setConfirmAction({ type: 'delete', runId: r.run_id })}
                      className="text-gray-400 hover:text-gray-600 text-xs"
                      title="删除"
                    >&#128465;</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {/* Pagination */}
        {data && data.total > pageSize && (
          <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50 text-sm">
            <span className="text-gray-500">共 {data.total} 条</span>
            <div className="flex gap-2">
              <button
                className="px-3 py-1 rounded border bg-white hover:bg-gray-100 disabled:opacity-40"
                disabled={page === 0}
                onClick={() => setPage(p => p - 1)}
              >上一页</button>
              <span className="px-3 py-1 text-gray-600">
                第 {page + 1} / {Math.ceil(data.total / pageSize)} 页
              </span>
              <button
                className="px-3 py-1 rounded border bg-white hover:bg-gray-100 disabled:opacity-40"
                disabled={(page + 1) * pageSize >= data.total}
                onClick={() => setPage(p => p + 1)}
              >下一页</button>
            </div>
          </div>
        )}
      </div>

      {/* Detail panel */}
      {selectedId && (
        <div>
          <div className="flex gap-1 mb-4 border-b border-gray-200">
            {TABS.map(({ id, label }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
                  tab === id
                    ? 'border-brand-600 text-brand-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Overview Tab */}
          {tab === 'overview' && (
            <div className="space-y-4">
              {/* Export HTML Report button */}
              {selectedId && (
                <div className="flex justify-end gap-2">
                  <a
                    href={`/api/v1/backtests/${selectedId}/export`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-secondary text-xs flex items-center gap-1"
                  >
                    📄 导出 HTML 报告
                  </a>
                  {detail?.status === 'completed' && (
                    <button
                      onClick={() => setShowDeployWizard(true)}
                      className="btn-primary text-xs flex items-center gap-1"
                    >
                      🚀 部署为模拟策略
                    </button>
                  )}
                  {detail?.status === 'completed' && (
                    <button
                      onClick={() => navigate('/factors', {
                        state: {
                          strategyContext: {
                            run_id: selectedId,
                            strategy_id: detail.strategy_id,
                            metrics: detail.metrics,
                          },
                        },
                      })}
                      className="btn-secondary text-xs flex items-center gap-1"
                    >
                      📊 优化因子权重
                    </button>
                  )}
                </div>
              )}
              {/* Parameter summary */}
              {detail?.strategy_config && (
                <div className="text-xs text-gray-400 flex flex-wrap gap-x-3 gap-y-1">
                  <span>市场: {marketLabel(detail.strategy_config.market_rule?.market)}</span>
                  <span>复权: {adjLabel(detail.strategy_config.market_rule?.adj_type)}</span>
                  <span>调仓: {rebalanceLabel(detail.strategy_config.rebalance_frequency)}</span>
                  <span>Sizer: {detail.strategy_config.sizer ?? 'equal_weight'}</span>
                </div>
              )}
              {/* Metrics cards */}
              {detail?.metrics && (
                <>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                    <MetricCard
                      label="总收益"
                      value={`${(detail.metrics.total_return * 100).toFixed(1)}%`}
                      warn={detail.metrics.total_return < 0}
                    />
                    <MetricCard
                      label="年化收益"
                      value={`${(detail.metrics.annualized_return * 100).toFixed(1)}%`}
                      warn={detail.metrics.annualized_return < 0}
                    />
                    <MetricCard
                      label="Sharpe"
                      value={Number(detail.metrics.sharpe_ratio ?? 0).toFixed(3)}
                      warn={detail.metrics.sharpe_ratio < 0}
                    />
                    <MetricCard
                      label="最大回撤"
                      value={`${(detail.metrics.max_drawdown * 100).toFixed(1)}%`}
                      warn={detail.metrics.max_drawdown < -0.2}
                    />
                    <MetricCard
                      label="胜率"
                      value={`${(detail.metrics.win_rate * 100).toFixed(1)}%`}
                    />
                    <MetricCard
                      label="交易次数"
                      value={String(detail.metrics.total_trades)}
                    />
                  </div>

                  {/* 主动管理指标（有值才显示）*/}
                  {(
                    detail.metrics.information_ratio != null ||
                    detail.metrics.omega_ratio != null ||
                    detail.metrics.tail_ratio != null
                  ) && (
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                      <MetricCard
                        label="信息比率"
                        value={detail.metrics.information_ratio != null
                          ? detail.metrics.information_ratio.toFixed(3)
                          : '—'}
                        sub="IR（需基准）"
                        warn={detail.metrics.information_ratio != null && detail.metrics.information_ratio < 0}
                      />
                      <MetricCard
                        label="跟踪误差"
                        value={detail.metrics.tracking_error != null
                          ? `${(detail.metrics.tracking_error * 100).toFixed(2)}%`
                          : '—'}
                        sub="TE（年化）"
                      />
                      <MetricCard
                        label="Alpha"
                        value={detail.metrics.alpha != null
                          ? `${(detail.metrics.alpha * 100).toFixed(2)}%`
                          : '—'}
                        sub="Jensen's α"
                        warn={detail.metrics.alpha != null && detail.metrics.alpha < 0}
                      />
                      <MetricCard
                        label="Omega Ratio"
                        value={detail.metrics.omega_ratio != null
                          ? detail.metrics.omega_ratio.toFixed(3)
                          : '—'}
                        warn={detail.metrics.omega_ratio != null && detail.metrics.omega_ratio < 1}
                      />
                      <MetricCard
                        label="Tail Ratio"
                        value={detail.metrics.tail_ratio != null
                          ? detail.metrics.tail_ratio.toFixed(3)
                          : '—'}
                      />
                      <MetricCard
                        label="换手率"
                        value={detail.metrics.turnover_pct != null
                          ? `${(detail.metrics.turnover_pct * 100).toFixed(1)}%`
                          : '—'}
                        sub="单边均值"
                      />
                    </div>
                  )}

                  {/* 导出指标按钮 */}
                  <div className="flex justify-end">
                    <button
                      className="btn-secondary text-sm"
                      onClick={() => downloadJson(
                        detail.metrics,
                        `metrics_${selectedId?.slice(0, 8) ?? 'backtest'}.json`,
                      )}
                    >
                      导出指标 JSON
                    </button>
                  </div>
                </>
              )}

              {/* Risk snapshot */}
              {riskData?.items?.[0] && (
                <div className="card">
                  <h3 className="text-sm font-semibold text-gray-700 mb-3">最新风险快照</h3>
                  <div className="grid grid-cols-4 gap-4">
                    <MetricCard label="回撤" value={`${((riskData.items[0].drawdown as number ?? 0) * 100).toFixed(2)}%`} warn />
                    <MetricCard label="杠杆" value={(riskData.items[0].gross_leverage as number ?? 0).toFixed(2)} />
                    <MetricCard label="VaR 95%" value={`${((riskData.items[0].var_95 as number ?? 0) * 100).toFixed(2)}%`} />
                    <MetricCard label="Beta" value={(riskData.items[0].beta as number ?? 0).toFixed(2)} />
                  </div>
                </div>
              )}

              {/* Analysis summary */}
              {analysis && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <MetricCard label="PSR" value={psr.toFixed(3)} sub="概率夏普比" warn={psr < 0.5} />
                    <MetricCard label="DSR" value={dsr.toFixed(3)} sub="修正夏普比" warn={dsr < 0.5} />
                    <MetricCard label="分析摘要" value={String(analysis.summary ?? '').slice(0, 60) || '—'} sub="" />
                    <MetricCard label="过拟合风险" value={`${Math.round(overfitScore * 100)}%`} warn={overfitScore > 0.5} />
                  </div>
                  <div className="card text-sm text-gray-700">
                    <div className="font-medium mb-1">分析摘要</div>
                    <p className="text-gray-600">{String(analysis.summary ?? '暂无分析摘要')}</p>
                  </div>
                </div>
              )}

              {!detail?.metrics && !analysis && (
                <div className="card text-center text-gray-400 py-12">
                  <div className="text-4xl mb-3">📊</div>
                  <div>选择一个已完成的回测查看详情</div>
                </div>
              )}
            </div>
          )}

          {/* Tearsheet Tab */}
          {tab === 'tearsheet' && (
            <div className="space-y-4">
              {pnlData.length > 0 ? (
                <div className="card">
                  <h3 className="font-semibold text-gray-800 mb-3">NAV & 回撤曲线</h3>
                  <PnLChart data={pnlData} height={280} showDrawdown />
                </div>
              ) : (
                <div className="card text-center text-gray-400 py-12">
                  <div className="text-4xl mb-3">📈</div>
                  <div>Tearsheet 数据加载中…</div>
                  <div className="text-xs mt-1">需要完整的 portfolio_returns 存储后才能显示 NAV 曲线</div>
                </div>
              )}

              {/* Benchmark overlay chart */}
              {combinedNav.length > 0 && benchmarkNav.length > 0 && (
                <div className="card">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-semibold text-gray-800">与基准对比</h3>
                    {(() => {
                      const lastPortfolio = combinedNav[combinedNav.length - 1]?.portfolio ?? 1
                      const lastBm = benchmarkNav[benchmarkNav.length - 1]?.nav ?? 1
                      const excess = (lastPortfolio / lastBm - 1) * 100
                      return (
                        <div className="text-sm text-gray-600">
                          超额收益：
                          <span className={`font-mono font-semibold ml-1 ${excess >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                            {excess >= 0 ? '+' : ''}{excess.toFixed(2)}%
                          </span>
                          <span className="text-xs text-gray-400 ml-1">vs {benchmarkAssetId}</span>
                        </div>
                      )
                    })()}
                  </div>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={combinedNav} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                      <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd"
                        tickFormatter={v => String(v).slice(5)} />
                      <YAxis tick={{ fontSize: 10 }} tickFormatter={v => v.toFixed(2)} />
                      <Tooltip formatter={(v: number) => v.toFixed(4)} />
                      <Legend />
                      <Line dataKey="portfolio" name="策略" stroke="#3b82f6" dot={false} strokeWidth={2} />
                      <Line dataKey="benchmark" name={benchmarkAssetId || '基准'} stroke="#94a3b8"
                        strokeDasharray="5 3" dot={false} strokeWidth={1.5} connectNulls />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Excess Return Cumulative Curve */}
              {combinedNav.length > 0 && benchmarkNav.length > 0 && (() => {
                const excessData = combinedNav
                  .filter(d => d.benchmark !== null && d.benchmark > 0)
                  .map(d => ({
                    date: d.date,
                    excess: ((d.portfolio as number) / (d.benchmark as number) - 1) * 100,
                  }))
                if (excessData.length === 0) return null
                return (
                  <div className="card">
                    <h3 className="font-semibold text-gray-800 mb-3">累计超额收益曲线</h3>
                    <ResponsiveContainer width="100%" height={200}>
                      <AreaChart data={excessData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd"
                          tickFormatter={v => String(v).slice(5)} />
                        <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${v.toFixed(1)}%`} />
                        <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
                        <ReferenceLine y={0} stroke="#e5e7eb" />
                        <Area type="monotone" dataKey="excess" name="超额收益" stroke="#10b981" fill="#d1fae5" fillOpacity={0.6} dot={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                )
              })()}

              {/* Rolling Tracking Error & Information Ratio */}
              {combinedNav.length > 0 && benchmarkNav.length > 0 && (() => {
                const validData = combinedNav.filter(d => d.benchmark !== null && d.benchmark > 0)
                if (validData.length < 21) return null

                // Compute rolling 20-day tracking error and IR
                const window = 20
                const rollingData: { date: string; te: number; ir: number }[] = []
                for (let i = window; i < validData.length; i++) {
                  const windowSlice = validData.slice(i - window, i)
                  const excessRets = windowSlice.map(d =>
                    (d.portfolio as number) / (d.benchmark as number) - 1
                  )
                  const mean = excessRets.reduce((a, b) => a + b, 0) / excessRets.length
                  const variance = excessRets.reduce((a, b) => a + (b - mean) ** 2, 0) / (excessRets.length - 1)
                  const te = Math.sqrt(variance) * Math.sqrt(252) // annualized
                  const ir = te > 0 ? (mean * 252) / te : 0 // annualized IR
                  rollingData.push({ date: validData[i].date, te: te * 100, ir })
                }

                if (rollingData.length === 0) return null
                return (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div className="card">
                      <h3 className="font-semibold text-gray-800 mb-3">滚动跟踪误差 (20日)</h3>
                      <ResponsiveContainer width="100%" height={200}>
                        <LineChart data={rollingData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd"
                            tickFormatter={v => String(v).slice(5)} />
                          <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${v.toFixed(1)}%`} />
                          <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
                          <Line type="monotone" dataKey="te" name="跟踪误差" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="card">
                      <h3 className="font-semibold text-gray-800 mb-3">滚动信息比率 (20日)</h3>
                      <ResponsiveContainer width="100%" height={200}>
                        <LineChart data={rollingData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd"
                            tickFormatter={v => String(v).slice(5)} />
                          <YAxis tick={{ fontSize: 10 }} />
                          <Tooltip formatter={(v: number) => v.toFixed(3)} />
                          <ReferenceLine y={0} stroke="#e5e7eb" />
                          <Line type="monotone" dataKey="ir" name="信息比率" stroke="#8b5cf6" dot={false} strokeWidth={1.5} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )
              })()}

              {/* Up/Down Capture Ratio */}
              {combinedNav.length > 0 && benchmarkNav.length > 0 && (() => {
                const validData = combinedNav.filter(d => d.benchmark !== null && d.benchmark > 1)
                if (validData.length < 2) return null

                let upPort = 0, upBm = 0, upCount = 0
                let downPort = 0, downBm = 0, downCount = 0
                for (let i = 1; i < validData.length; i++) {
                  const bmRet = (validData[i].benchmark as number) / (validData[i - 1].benchmark as number) - 1
                  const portRet = (validData[i].portfolio as number) / (validData[i - 1].portfolio as number) - 1
                  if (bmRet > 0) {
                    upPort += portRet
                    upBm += bmRet
                    upCount++
                  } else if (bmRet < 0) {
                    downPort += portRet
                    downBm += bmRet
                    downCount++
                  }
                }

                const upCapture = upCount > 0 && upBm > 0 ? (upPort / upBm) * 100 : 0
                const downCapture = downCount > 0 && downBm < 0 ? (downPort / downBm) * 100 : 0

                return (
                  <div className="card">
                    <h3 className="font-semibold text-gray-800 mb-3">上涨/下跌捕获率</h3>
                    <div className="grid grid-cols-4 gap-4">
                      <MetricCard label="上涨捕获率" value={`${upCapture.toFixed(1)}%`} sub={`${upCount} 个上涨日`} />
                      <MetricCard label="下跌捕获率" value={`${downCapture.toFixed(1)}%`} sub={`${downCount} 个下跌日`} warn={downCapture > 100} />
                      <MetricCard label="上涨参与日" value={String(upCount)} sub="基准上涨时策略也上涨" />
                      <MetricCard label="下跌参与日" value={String(downCount)} sub="基准下跌时策略也下跌" />
                    </div>
                  </div>
                )
              })()}

              {tearsheet && (
                <div className="card">
                  <h3 className="font-semibold text-gray-800 mb-3">原始数据（JSON）</h3>
                  <pre className="text-xs text-gray-500 overflow-x-auto bg-gray-50 rounded-lg p-3">
                    {JSON.stringify(tearsheet, null, 2).slice(0, 1000)}…
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Overfitting Tab */}
          {tab === 'overfitting' && (
            <div className="space-y-4">
              {analysis && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <OverfitScore score={overfitScore} />
                  <MetricCard label="PSR（概率夏普）" value={psr.toFixed(3)} sub="越接近1越显著" warn={psr < 0.5} />
                  <MetricCard label="DSR（修正夏普）" value={dsr.toFixed(3)} sub="多次试验修正后" warn={dsr < 0.5} />
                </div>
              )}

              {/* Walk-forward fold metrics */}
              {wfWindows.length > 0 && (
                <FoldMetricsCard folds={wfWindows as Record<string, unknown>[]} />
              )}

              {/* Walk-forward Sharpe bar chart */}
              {wfChartData.length > 0 && (
                <div className="card">
                  <h3 className="font-semibold text-gray-800 mb-3">Walk-forward OOS 夏普比（{wfChartData.length} 个窗口）</h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={wfChartData}>
                      <XAxis dataKey="window" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip formatter={(v: number) => v.toFixed(3)} />
                      <ReferenceLine y={0} stroke="#e5e7eb" />
                      <Bar dataKey="sharpe" name="Sharpe">
                        {wfChartData.map((_: unknown, i: number) => (
                          <Cell key={i} fill={wfChartData[i].sharpe > 0 ? '#4f63d2' : '#ef4444'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* CPCV windows summary */}
              {cpvcWindows.length > 0 && (
                <div className="card">
                  <h3 className="font-semibold text-gray-800 mb-3">CPCV 验证窗口（{cpvcWindows.length} 个组合）</h3>
                  <div className="grid grid-cols-4 gap-2">
                    {(cpvcWindows as Record<string, unknown>[]).slice(0, 8).map((w, i) => {
                      const metrics = w.metrics_json as Record<string, number> | null
                      const sr = metrics?.sharpe ?? 0
                      return (
                        <div key={i} className={`text-center p-2 rounded-lg text-xs ${sr > 0 ? 'bg-green-50' : 'bg-red-50'}`}>
                          <div className={`font-bold ${sr > 0 ? 'text-green-700' : 'text-red-700'}`}>{sr.toFixed(2)}</div>
                          <div className="text-gray-400">C{i + 1}</div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Multiple testing */}
              {multipleTestData && Object.keys(multipleTestData).length > 0 && (
                <div className="card">
                  <h3 className="font-semibold text-gray-800 mb-3">多重检验修正</h3>
                  <div className="space-y-2">
                    {Object.entries(multipleTestData).map(([method, result]) => {
                      const r = result as Record<string, unknown>
                      return (
                        <div key={method} className="flex items-center justify-between text-sm">
                          <span className="text-gray-600 capitalize">{method.replace('_', '-')}</span>
                          <span className={`badge ${r.any_significant ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                            {r.any_significant ? '显著' : '不显著'}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {!analysis && !validationData && !multipleTestData && selectedId && (
                <div className="card text-center py-12">
                  <div className="text-4xl mb-3">🔬</div>
                  <div className="text-gray-500 mb-2">暂无过拟合分析数据</div>
                  <p className="text-xs text-gray-400 mb-4">
                    分析会在回测完成后自动触发，如果尚未生成，可手动重新运行
                  </p>
                  <button
                    className="btn-primary"
                    onClick={async () => {
                      try {
                        await backtestsApi.triggerAnalysis(selectedId)
                        toast.info('分析任务已提交，约 30 秒后刷新查看结果')
                      } catch (e) {
                        toast.error(`触发分析失败：${(e as Error).message}`)
                      }
                    }}
                  >
                    重新分析
                  </button>
                  <p className="text-xs text-gray-400 mt-2">分析包含 PSR/DSR/CPCV 过拟合检测</p>
                </div>
              )}
            </div>
          )}

          {/* Fills Tab */}
          {tab === 'fills' && (
            <div className="space-y-3">
              {/* 导出 CSV 按钮 */}
              {fillsData && fillsData.items.length > 0 && (
                <div className="flex justify-end">
                  <button
                    className="btn-secondary text-sm"
                    onClick={() => downloadCsv(
                      (fillsData.items as unknown) as Record<string, unknown>[],
                      `fills_${selectedId?.slice(0, 8) ?? 'backtest'}.csv`,
                    )}
                  >
                    导出 CSV
                  </button>
                </div>
              )}

              <DataTable
                data={(fillsData?.items ?? []) as unknown as Record<string, unknown>[]}
                rowKey={(r) => `${r.trade_date}_${r.asset_id}_${r.order_idx ?? ''}`}
                pageSize={fillsPageSize}
                emptyText="暂无交易记录"
                rowClassName={(row: Record<string, unknown>) =>
                  row.reason === 'delist_forced_liquidation' ? 'bg-orange-50' : ''
                }
                backendPagination={fillsData ? {
                  total: fillsData.total,
                  page: fillsPage,
                  onPageChange: setFillsPage,
                } : undefined}
                columns={[
                  { key: 'trade_date', label: '日期', sortable: true, width: '100px',
                    render: (v) => <span className="text-xs">{String(v ?? '').slice(0, 10)}</span> },
                  { key: 'asset_id', label: '资产', sortable: true, searchable: true,
                    render: (v) => <span className="font-mono text-xs">{String(v)}</span> },
                  { key: 'side', label: '方向', sortable: true, filterable: true, filters: ['buy', 'sell'],
                    render: (v) => (
                      <span className={`badge ${v === 'buy' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}`}>
                        {v === 'buy' ? '买入' : '卖出'}
                      </span>
                    ) },
                  { key: 'qty', label: '数量', sortable: true, width: '80px',
                    render: (v) => <span className="text-right block">{Number(v).toLocaleString()}</span> },
                  { key: 'price', label: '价格', sortable: true, width: '80px',
                    render: (v) => <span className="text-right block">{Number(v).toFixed(2)}</span> },
                  { key: 'notional', label: '金额', sortable: true, width: '120px',
                    render: (v) => <span className="text-right block">{Number(v).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span> },
                  { key: 'total_cost', label: '费用', sortable: true, width: '80px',
                    render: (v) => <span className="text-right block text-gray-500">{Number(v).toFixed(2)}</span> },
                  { key: 'reason', label: '原因', width: '120px',
                    render: (v: unknown) => {
                      if (v === 'delist_forced_liquidation') return <span className="text-orange-600 font-medium">退市强制平仓</span>
                      return <span className="text-gray-400">—</span>
                    } },
                ]}
              />
            </div>
          )}

          {tab === 'tca' && (
            <div className="space-y-4">
              {tcaData ? (
                <>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <MetricCard label="总成本" value={`¥${Number(tcaData.total_cost ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`} />
                    <MetricCard label="成本率" value={`${Number(tcaData.cost_pct_turnover ?? 0).toFixed(4)}%`} />
                    <MetricCard label="交易笔数" value={String(tcaData.num_trades ?? 0)} />
                    <MetricCard label="平均成本/笔" value={`¥${Number(tcaData.cost_per_trade ?? 0).toFixed(2)}`} />
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="card p-4">
                      <div className="text-xs text-gray-500 mb-1">佣金</div>
                      <div className="text-lg font-semibold">¥{Number(tcaData.total_commission ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</div>
                    </div>
                    <div className="card p-4">
                      <div className="text-xs text-gray-500 mb-1">印花税</div>
                      <div className="text-lg font-semibold">¥{Number(tcaData.total_stamp_duty ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</div>
                    </div>
                    <div className="card p-4">
                      <div className="text-xs text-gray-500 mb-1">滑点</div>
                      <div className="text-lg font-semibold">¥{Number(tcaData.total_slippage ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center text-gray-400 py-12">无交易数据，无法进行成本分析</div>
              )}
            </div>
          )}

          {tab === 'attribution' && (
            <div className="space-y-4">
              {attributionData ? (
                <>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <MetricCard label="超额收益" value={`${Number(attributionData.active_return ?? 0 * 100).toFixed(2)}%`} warn={Number(attributionData.active_return ?? 0) < 0} />
                    <MetricCard label="配置效应" value={`${(Number(attributionData.allocation_effect ?? 0) * 100).toFixed(2)}%`} />
                    <MetricCard label="选股效应" value={`${(Number(attributionData.selection_effect ?? 0) * 100).toFixed(2)}%`} />
                    <MetricCard label="交互效应" value={`${(Number(attributionData.interaction_effect ?? 0) * 100).toFixed(2)}%`} />
                  </div>
                  {Object.keys(attributionData.sector_details as Record<string, unknown> ?? {}).length > 0 && (
                    <div className="card p-4">
                      <div className="text-sm font-medium text-gray-700 mb-3">行业归因明细</div>
                      <table className="w-full text-xs">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="table-th">行业</th>
                            <th className="table-th">组合权重</th>
                            <th className="table-th">基准权重</th>
                            <th className="table-th">组合收益</th>
                            <th className="table-th">基准收益</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(attributionData.sector_details as Record<string, Record<string, number>>).map(([sector, data]) => (
                            <tr key={sector} className="table-row">
                              <td className="table-td">{sector}</td>
                              <td className="table-td">{((data.port_weight ?? 0) * 100).toFixed(1)}%</td>
                              <td className="table-td">{((data.bench_weight ?? 0) * 100).toFixed(1)}%</td>
                              <td className="table-td">{((data.port_return ?? 0) * 100).toFixed(2)}%</td>
                              <td className="table-td">{((data.bench_return ?? 0) * 100).toFixed(2)}%</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center text-gray-400 py-12">未设置基准或组合为单资产，无法进行归因分析</div>
              )}
            </div>
          )}

          {/* Risk Analysis Tab */}
          {tab === 'risk' && (
            <div className="space-y-4">
              {riskRollingData ? (
                <>
                  {/* Latest metrics cards */}
                  {(() => {
                    const data = riskRollingData.data as Record<string, unknown>[] | undefined
                    const latest = data?.[data.length - 1]
                    if (!latest) return null
                    return (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                        <MetricCard label="VaR 95%" value={`${((latest.var_95 as number ?? 0) * 100).toFixed(2)}%`} warn />
                        <MetricCard label="CVaR 95%" value={`${((latest.cvar_95 as number ?? 0) * 100).toFixed(2)}%`} warn />
                        <MetricCard label="年化波动率" value={`${((latest.volatility as number ?? 0) * 100).toFixed(2)}%`} />
                        <MetricCard label="Sharpe" value={Number(latest.sharpe_ratio ?? 0).toFixed(3)} />
                      </div>
                    )
                  })()}

                  {/* Window selector */}
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-gray-500">滚动窗口：</span>
                    {[20, 60, 252].map(w => (
                      <button
                        key={w}
                        onClick={() => setRiskWindow(w)}
                        className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                          riskWindow === w
                            ? 'bg-brand-600 text-white'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        }`}
                      >
                        {w}日
                      </button>
                    ))}
                  </div>

                  {/* Rolling VaR / CVaR chart */}
                  <div className="card">
                    <h3 className="font-semibold text-gray-800 mb-3">滚动 VaR / CVaR</h3>
                    <ResponsiveContainer width="100%" height={240}>
                      <LineChart data={riskRollingData.data as Record<string, unknown>[]} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="trade_date" tick={{ fontSize: 10 }} interval="preserveStartEnd" tickFormatter={v => String(v).slice(5)} />
                        <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${(v * 100).toFixed(1)}%`} />
                        <Tooltip formatter={(v: number) => `${(v * 100).toFixed(3)}%`} />
                        <Legend />
                        <Line type="monotone" dataKey="var_95" name="VaR 95%" stroke="#ef4444" dot={false} strokeWidth={1.5} />
                        <Line type="monotone" dataKey="cvar_95" name="CVaR 95%" stroke="#dc2626" dot={false} strokeWidth={1.5} strokeDasharray="4 2" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Rolling volatility + Sharpe side by side */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div className="card">
                      <h3 className="font-semibold text-gray-800 mb-3">滚动波动率</h3>
                      <ResponsiveContainer width="100%" height={200}>
                        <LineChart data={riskRollingData.data as Record<string, unknown>[]} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis dataKey="trade_date" tick={{ fontSize: 10 }} interval="preserveStartEnd" tickFormatter={v => String(v).slice(5)} />
                          <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${(v * 100).toFixed(1)}%`} />
                          <Tooltip formatter={(v: number) => `${(v * 100).toFixed(3)}%`} />
                          <Line type="monotone" dataKey="volatility" name="波动率" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="card">
                      <h3 className="font-semibold text-gray-800 mb-3">滚动 Sharpe</h3>
                      <ResponsiveContainer width="100%" height={200}>
                        <LineChart data={riskRollingData.data as Record<string, unknown>[]} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis dataKey="trade_date" tick={{ fontSize: 10 }} interval="preserveStartEnd" tickFormatter={v => String(v).slice(5)} />
                          <YAxis tick={{ fontSize: 10 }} />
                          <Tooltip formatter={(v: number) => v.toFixed(3)} />
                          <ReferenceLine y={0} stroke="#e5e7eb" />
                          <Line type="monotone" dataKey="sharpe_ratio" name="Sharpe" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  {/* Drawdown underwater chart */}
                  {drawdownTsData && (drawdownTsData.data as Record<string, unknown>[])?.length > 0 && (
                    <div className="card">
                      <h3 className="font-semibold text-gray-800 mb-3">回撤水下图</h3>
                      <ResponsiveContainer width="100%" height={200}>
                        <AreaChart data={drawdownTsData.data as Record<string, unknown>[]} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis dataKey="trade_date" tick={{ fontSize: 10 }} interval="preserveStartEnd" tickFormatter={v => String(v).slice(5)} />
                          <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${(v * 100).toFixed(1)}%`} />
                          <Tooltip formatter={(v: number) => `${(v * 100).toFixed(3)}%`} />
                          <Area type="monotone" dataKey="drawdown" name="回撤" stroke="#ef4444" fill="#fef2f2" fillOpacity={0.6} dot={false} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {/* Return distribution histogram */}
                  {returnDistData && (returnDistData.data as Record<string, unknown>[])?.length > 0 && (
                    <div className="card">
                      <h3 className="font-semibold text-gray-800 mb-3">收益率分布</h3>
                      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-3">
                        <MetricCard label="均值" value={`${((returnDistData.stats as Record<string, number>)?.mean * 100).toFixed(3)}%`} />
                        <MetricCard label="标准差" value={`${((returnDistData.stats as Record<string, number>)?.std * 100).toFixed(3)}%`} />
                        <MetricCard label="偏度" value={(returnDistData.stats as Record<string, number>)?.skewness?.toFixed(3) ?? '—'} />
                        <MetricCard label="峰度" value={(returnDistData.stats as Record<string, number>)?.kurtosis?.toFixed(3) ?? '—'} />
                        <MetricCard label="极值" value={`${((returnDistData.stats as Record<string, number>)?.min * 100).toFixed(2)}% ~ ${((returnDistData.stats as Record<string, number>)?.max * 100).toFixed(2)}%`} />
                      </div>
                      <ResponsiveContainer width="100%" height={200}>
                        <BarChart data={returnDistData.data as Record<string, unknown>[]} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis dataKey="bin_label" tick={{ fontSize: 9 }} interval={Math.floor((returnDistData.data as unknown[])?.length / 8) || 1} />
                          <YAxis tick={{ fontSize: 10 }} />
                          <Tooltip formatter={(v: number) => `${v} 次`} />
                          <Bar dataKey="count" name="频次" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {/* Drawdown events table */}
                  {drawdownsData && (drawdownsData.periods as Record<string, unknown>[])?.length > 0 && (
                    <div className="card p-0 overflow-hidden">
                      <div className="px-4 pt-3 pb-2 font-semibold text-gray-800 text-sm">回撤事件</div>
                      <table className="w-full text-xs">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="table-th">编号</th>
                            <th className="table-th">开始</th>
                            <th className="table-th">谷底</th>
                            <th className="table-th">恢复</th>
                            <th className="table-th">最大回撤</th>
                            <th className="table-th">持续天数</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(drawdownsData.periods as Record<string, unknown>[]).map((p, i) => (
                            <tr key={i} className="table-row">
                              <td className="table-td font-mono">{p.period_id ?? i + 1}</td>
                              <td className="table-td">{String(p.peak_date ?? '').slice(0, 10)}</td>
                              <td className="table-td">{String(p.trough_date ?? '').slice(0, 10)}</td>
                              <td className="table-td">{p.recovery_date ? String(p.recovery_date).slice(0, 10) : '未恢复'}</td>
                              <td className="table-td text-red-600 font-medium">{((p.max_drawdown as number ?? 0) * 100).toFixed(2)}%</td>
                              <td className="table-td">{p.duration_days ?? '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Correlation Heatmap */}
                  {correlationData && (correlationData.assets as string[])?.length > 0 && (
                    <div className="card">
                      <h3 className="font-semibold text-gray-800 mb-3">资产相关性矩阵</h3>
                      <div className="overflow-x-auto">
                        <table className="text-xs">
                          <thead>
                            <tr>
                              <th className="px-2 py-1"></th>
                              {(correlationData.assets as string[]).map(a => (
                                <th key={a} className="px-2 py-1 font-mono text-gray-600">{a.slice(0, 6)}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {(correlationData.assets as string[]).map(row => (
                              <tr key={row}>
                                <td className="px-2 py-1 font-mono text-gray-600">{row.slice(0, 6)}</td>
                                {(correlationData.assets as string[]).map(col => {
                                  const val = (correlationData.matrix as Record<string, Record<string, number>>)?.[row]?.[col]
                                  return (
                                    <td key={col} className="px-2 py-1 text-center" style={{
                                      backgroundColor: val == null ? '#f3f4f6'
                                        : val > 0 ? `rgba(34,197,94,${Math.abs(val) * 0.8})`
                                        : `rgba(239,68,68,${Math.abs(val) * 0.8})`,
                                      color: Math.abs(val ?? 0) > 0.5 ? 'white' : '#374151'
                                    }}>
                                      {val != null ? val.toFixed(2) : '—'}
                                    </td>
                                  )
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Factor Exposure */}
                  {factorExposureData && (factorExposureData.data as Record<string, unknown>[])?.length > 0 && (
                    <div className="card">
                      <h3 className="font-semibold text-gray-800 mb-3">因子暴露</h3>
                      <ResponsiveContainer width="100%" height={240}>
                        <AreaChart data={factorExposureData.data as Record<string, unknown>[]} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis dataKey="trade_date" tick={{ fontSize: 10 }} interval="preserveStartEnd" tickFormatter={v => String(v).slice(5)} />
                          <YAxis tick={{ fontSize: 10 }} />
                          <Tooltip />
                          <Legend />
                          <Area type="monotone" dataKey={(factorExposureData.keys as string[])?.[0] ?? 'momentum_20d'} name="动量" stroke="#3b82f6" fill="#dbeafe" fillOpacity={0.6} dot={false} />
                          <Area type="monotone" dataKey={(factorExposureData.keys as string[])?.[1] ?? 'volatility_20d'} name="波动率" stroke="#f59e0b" fill="#fef3c7" fillOpacity={0.6} dot={false} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {/* Stress Test */}
                  {stressTestData && (stressTestData.scenarios as Record<string, unknown>[])?.length > 0 && (
                    <div className="card">
                      <h3 className="font-semibold text-gray-800 mb-3">压力测试</h3>
                      <ResponsiveContainer width="100%" height={240}>
                        <BarChart
                          data={(stressTestData.scenarios as Record<string, unknown>[]).map(s => ({
                            ...s,
                            impact_pct: (s.impact as number) * 100,
                          }))}
                          layout="vertical"
                          margin={{ top: 4, right: 16, left: 100, bottom: 0 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={v => `${v.toFixed(1)}%`} />
                          <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={100} />
                          <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
                          <Bar dataKey="impact_pct" name="影响" radius={[0, 4, 4, 0]}>
                            {(stressTestData.scenarios as Record<string, unknown>[]).map((_, i) => (
                              <Cell key={i} fill={i === 5 ? '#8b5cf6' : '#ef4444'} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {/* Risk Contribution Pie */}
                  {riskContribData && (riskContribData.contributions as Record<string, unknown>[])?.length > 0 && (
                    <div className="card">
                      <h3 className="font-semibold text-gray-800 mb-3">风险贡献</h3>
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <ResponsiveContainer width="100%" height={240}>
                          <PieChart>
                            <Pie
                              data={(riskContribData.contributions as Record<string, unknown>[]).slice(0, 10).map(c => ({
                                name: String(c.asset_id).slice(0, 6),
                                value: Math.abs(c.pct_of_risk as number) * 100,
                              }))}
                              cx="50%"
                              cy="50%"
                              outerRadius={80}
                              dataKey="value"
                              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                            >
                              {(riskContribData.contributions as Record<string, unknown>[]).slice(0, 10).map((_, i) => (
                                <Cell key={i} fill={['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1'][i]} />
                              ))}
                            </Pie>
                            <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
                          </PieChart>
                        </ResponsiveContainer>
                        <div className="text-sm">
                          <div className="text-gray-500 mb-2">组合波动率: {((riskContribData.portfolio_volatility as number ?? 0) * 100).toFixed(2)}%</div>
                          <div className="space-y-1 max-h-48 overflow-y-auto">
                            {(riskContribData.contributions as Record<string, unknown>[]).slice(0, 10).map((c, i) => (
                              <div key={i} className="flex justify-between">
                                <span className="font-mono text-xs">{String(c.asset_id).slice(0, 8)}</span>
                                <span className="text-gray-600">{((c.pct_of_risk as number) * 100).toFixed(1)}%</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="card text-center text-gray-400 py-12">
                  <div className="text-4xl mb-3">📉</div>
                  <div className="text-gray-500 mb-2">暂无风险分析数据</div>
                  <p className="text-xs text-gray-400">风险数据在回测完成后自动生成，包含滚动风险指标和回撤分析</p>
                </div>
              )}
            </div>
          )}

          {/* Model Compare Tab */}
          {tab === 'model_compare' && selectedId && (
            <ModelCompareTab backtestId={selectedId} selectedModels={compareIds} />
          )}

          {/* Feature Importance Tab */}
          {tab === 'feature_importance' && selectedId && (
            <FeatureImportanceTab modelVersion={selectedId} />
          )}

          {/* Model Diagnostics Tab */}
          {tab === 'model_diagnostics' && selectedId && (
            <ModelDiagnosticsTab modelVersion={selectedId} />
          )}

          {/* Advanced Analysis Tab */}
          {tab === 'advanced' && (
            <div className="space-y-4">
              {/* Calendar Analysis */}
              {calendarAnalysisData ? (
                <>
                  {/* Month Effect Heatmap */}
                  {calendarAnalysisData.month_effects && (calendarAnalysisData.month_effects as unknown[]).length > 0 && (
                    <div className="card">
                      <h3 className="font-semibold text-gray-800 mb-3">月份效应</h3>
                      <div className="grid grid-cols-6 gap-2">
                        {(calendarAnalysisData.month_effects as { month: number; label: string; mean_return: number; win_rate: number; count: number }[]).map(m => {
                          const color = m.mean_return > 0
                            ? `rgba(34, 197, 94, ${Math.min(Math.abs(m.mean_return) * 100, 0.8)})`
                            : m.mean_return < 0
                              ? `rgba(239, 68, 68, ${Math.min(Math.abs(m.mean_return) * 100, 0.8)})`
                              : '#f3f4f6'
                          return (
                            <div key={m.month} className="text-center p-3 rounded-lg" style={{ backgroundColor: color }}>
                              <div className="text-sm font-medium">{m.label}</div>
                              <div className="text-lg font-bold mt-1">{(m.mean_return * 100).toFixed(2)}%</div>
                              <div className="text-xs text-gray-600 mt-0.5">胜率 {(m.win_rate * 100).toFixed(0)}%</div>
                              <div className="text-xs text-gray-400">{m.count} 日</div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Weekday Effect */}
                  {calendarAnalysisData.weekday_effects && (calendarAnalysisData.weekday_effects as unknown[]).length > 0 && (
                    <div className="card">
                      <h3 className="font-semibold text-gray-800 mb-3">星期效应</h3>
                      <ResponsiveContainer width="100%" height={200}>
                        <BarChart
                          data={(calendarAnalysisData.weekday_effects as { weekday: number; label: string; mean_return: number }[]).map(w => ({
                            ...w,
                            mean_return_pct: w.mean_return * 100,
                          }))}
                          margin={{ top: 4, right: 16, left: -20, bottom: 0 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                          <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${v.toFixed(2)}%`} />
                          <Tooltip formatter={(v: number) => `${v.toFixed(3)}%`} />
                          <ReferenceLine y={0} stroke="#e5e7eb" />
                          <Bar dataKey="mean_return_pct" name="平均收益" radius={[4, 4, 0, 0]}>
                            {(calendarAnalysisData.weekday_effects as { mean_return: number }[]).map((w, i) => (
                              <Cell key={i} fill={w.mean_return >= 0 ? '#22c55e' : '#ef4444'} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {/* Month-end effect */}
                  {calendarAnalysisData.month_end_effect && (
                    <div className="card">
                      <h3 className="font-semibold text-gray-800 mb-3">月末效应</h3>
                      <div className="grid grid-cols-4 gap-4">
                        <MetricCard
                          label="月末平均收益"
                          value={`${((calendarAnalysisData.month_end_effect as { month_end_mean: number }).month_end_mean * 100).toFixed(3)}%`}
                          sub={`${(calendarAnalysisData.month_end_effect as { month_end_count: number }).month_end_count} 个交易日`}
                        />
                        <MetricCard
                          label="非月末平均收益"
                          value={`${((calendarAnalysisData.month_end_effect as { non_month_end_mean: number }).non_month_end_mean * 100).toFixed(3)}%`}
                          sub={`${(calendarAnalysisData.month_end_effect as { non_month_end_count: number }).non_month_end_count} 个交易日`}
                        />
                        <MetricCard
                          label="t 统计量"
                          value={(calendarAnalysisData.month_end_effect as { t_statistic: number }).t_statistic.toFixed(3)}
                        />
                        <MetricCard
                          label="p 值"
                          value={(calendarAnalysisData.month_end_effect as { p_value: number }).p_value.toFixed(4)}
                          warn={(calendarAnalysisData.month_end_effect as { p_value: number }).p_value < 0.05}
                          sub={(calendarAnalysisData.month_end_effect as { p_value: number }).p_value < 0.05 ? '统计显著' : '不显著'}
                        />
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="card text-center text-gray-400 py-8">
                  <div className="text-2xl mb-2">📅</div>
                  <div>暂无日历分析数据</div>
                </div>
              )}

              {/* Trade Analysis */}
              {tradeAnalysisData ? (
                <>
                  {/* Profit Factor & Key Metrics */}
                  <div className="card">
                    <h3 className="font-semibold text-gray-800 mb-3">交易分析概览</h3>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                      <MetricCard
                        label="利润因子"
                        value={Number(tradeAnalysisData.profit_factor ?? 0).toFixed(2)}
                        sub="总盈利 / 总亏损"
                      />
                      <MetricCard
                        label="盈亏比"
                        value={Number(tradeAnalysisData.payoff_ratio ?? 0).toFixed(2)}
                        sub="平均盈利 / 平均亏损"
                      />
                      <MetricCard
                        label="期望收益"
                        value={Number(tradeAnalysisData.expectancy ?? 0).toFixed(4)}
                        sub="每笔交易期望"
                      />
                      <MetricCard
                        label="总交易次数"
                        value={String(tradeAnalysisData.total_trades ?? 0)}
                      />
                    </div>
                  </div>

                  {/* Win/Loss Stats */}
                  {tradeAnalysisData.win_loss_stats && (
                    <div className="card">
                      <h3 className="font-semibold text-gray-800 mb-3">盈亏统计</h3>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
                        <MetricCard
                          label="胜率"
                          value={`${((tradeAnalysisData.win_loss_stats as { win_rate: number }).win_rate * 100).toFixed(1)}%`}
                        />
                        <MetricCard
                          label="平均盈利"
                          value={`¥${Number((tradeAnalysisData.win_loss_stats as { avg_win: number }).avg_win).toLocaleString()}`}
                        />
                        <MetricCard
                          label="平均亏损"
                          value={`¥${Number((tradeAnalysisData.win_loss_stats as { avg_loss: number }).avg_loss).toLocaleString()}`}
                          warn
                        />
                        <MetricCard
                          label="最大单笔盈利"
                          value={`¥${Number((tradeAnalysisData.win_loss_stats as { largest_win: number }).largest_win).toLocaleString()}`}
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="p-3 bg-green-50 rounded-lg">
                          <div className="text-sm font-medium text-green-800">最长连胜</div>
                          <div className="text-2xl font-bold text-green-700">{(tradeAnalysisData.win_loss_stats as { max_win_streak: number }).max_win_streak} 笔</div>
                        </div>
                        <div className="p-3 bg-red-50 rounded-lg">
                          <div className="text-sm font-medium text-red-800">最长连亏</div>
                          <div className="text-2xl font-bold text-red-700">{(tradeAnalysisData.win_loss_stats as { max_loss_streak: number }).max_loss_streak} 笔</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Holding Period Distribution */}
                  {tradeAnalysisData.holding_period_stats && (tradeAnalysisData.holding_period_stats as { distribution: unknown[] }).distribution.length > 0 && (
                    <div className="card">
                      <h3 className="font-semibold text-gray-800 mb-3">持仓周期分布</h3>
                      <div className="grid grid-cols-4 gap-4 mb-4">
                        <MetricCard label="平均持仓" value={`${(tradeAnalysisData.holding_period_stats as { mean_days: number }).mean_days} 天`} />
                        <MetricCard label="中位数" value={`${(tradeAnalysisData.holding_period_stats as { median_days: number }).median_days} 天`} />
                        <MetricCard label="最短" value={`${(tradeAnalysisData.holding_period_stats as { min_days: number }).min_days} 天`} />
                        <MetricCard label="最长" value={`${(tradeAnalysisData.holding_period_stats as { max_days: number }).max_days} 天`} />
                      </div>
                      <ResponsiveContainer width="100%" height={180}>
                        <BarChart
                          data={(tradeAnalysisData.holding_period_stats as { distribution: { bucket: string; count: number }[] }).distribution}
                          margin={{ top: 4, right: 16, left: -20, bottom: 0 }}
                        >
                          <XAxis dataKey="bucket" tick={{ fontSize: 10 }} />
                          <YAxis tick={{ fontSize: 10 }} />
                          <Tooltip formatter={(v: number) => `${v} 笔`} />
                          <Bar dataKey="count" name="交易数" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </>
              ) : (
                <div className="card text-center text-gray-400 py-8">
                  <div className="text-2xl mb-2">📋</div>
                  <div>暂无交易分析数据</div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Walk-Forward Tab */}
      {selectedId && tab === 'walkforward' && (
        <div className="space-y-4">
          {!wfData ? (
            <p className="text-gray-400 text-sm">此回测不是 Walk-Forward 模式</p>
          ) : (
            <>
              {/* Aggregated metrics */}
              <div className="grid grid-cols-4 gap-4">
                <MetricCard label="平均 Sharpe" value={(wfData.aggregated.avg_sharpe_ratio ?? 0).toFixed(3)} />
                <MetricCard label="平均收益" value={`${((wfData.aggregated.avg_total_return ?? 0) * 100).toFixed(2)}%`} />
                <MetricCard label="最大回撤" value={`${((wfData.aggregated.avg_max_drawdown ?? 0) * 100).toFixed(2)}%`} warn />
                <MetricCard label="Fold 数" value={String(wfData.n_folds)} />
              </div>

              {/* Fold details table */}
              <div className="card p-0 overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      {['Fold', 'Train', 'OOS', 'Sharpe', '收益', '回撤', 'Win Rate'].map(h => (
                        <th key={h} className="table-th">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {wfData.folds.map(fold => (
                      <tr key={fold.fold_id} className="table-row">
                        <td className="table-td font-mono">{fold.fold_id + 1}</td>
                        <td className="table-td text-xs">{fold.train_start} ~ {fold.train_end}</td>
                        <td className="table-td text-xs">{fold.test_start} ~ {fold.test_end}</td>
                        <td className="table-td">{(fold.metrics?.sharpe_ratio as number)?.toFixed(3) ?? '—'}</td>
                        <td className="table-td">{((fold.metrics?.total_return as number ?? 0) * 100).toFixed(2)}%</td>
                        <td className="table-td text-red-600">{((fold.metrics?.max_drawdown as number ?? 0) * 100).toFixed(2)}%</td>
                        <td className="table-td">{((fold.metrics?.win_rate as number ?? 0) * 100).toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Timeline visualization */}
              <div className="card">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">时间线</h3>
                <div className="relative h-20 bg-gray-100 rounded">
                  {wfData.folds.map((fold, i) => {
                    const allDates = wfData.folds.flatMap(f => [f.train_start, f.test_end])
                    const minDate = new Date(allDates[0])
                    const maxDate = new Date(allDates[allDates.length - 1])
                    const totalMs = maxDate.getTime() - minDate.getTime()
                    const pct = (d: string) => ((new Date(d).getTime() - minDate.getTime()) / totalMs * 100)
                    return (
                      <div key={i} className="absolute w-full" style={{ top: `${i * 25}%`, height: '22%' }}>
                        <div className="absolute bg-blue-400 opacity-30 h-full rounded-l"
                          style={{ left: `${pct(fold.train_start)}%`, width: `${pct(fold.train_end) - pct(fold.train_start)}%` }} />
                        <div className="absolute bg-green-500 opacity-60 h-full rounded-r"
                          style={{ left: `${pct(fold.test_start)}%`, width: `${pct(fold.test_end) - pct(fold.test_start)}%` }} />
                      </div>
                    )
                  })}
                </div>
                <div className="flex gap-4 mt-2 text-xs text-gray-500">
                  <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-400 opacity-30 rounded" />Train</span>
                  <span className="flex items-center gap-1"><span className="w-3 h-3 bg-green-500 opacity-60 rounded" />OOS</span>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* 浮动对比按钮 */}
      {compareIds.length >= 2 && !showCompare && (
        <div className="fixed bottom-6 right-6 z-20 flex items-center gap-2">
          <button
            className="btn-primary shadow-lg flex items-center gap-2 px-5 py-2.5"
            onClick={() => setShowCompare(true)}
          >
            📊 对比 {compareIds.length} 个回测
          </button>
          <button className="btn-secondary text-xs" onClick={() => setCompareIds([])}>
            清除
          </button>
        </div>
      )}

      {/* 对比弹窗 */}
      {showCompare && (
        <div className="fixed inset-0 bg-black/40 z-30 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between p-5 border-b flex-shrink-0">
              <h2 className="text-lg font-semibold text-gray-800">
                多回测横向对比（{compareIds.length} 个）
              </h2>
              <button onClick={() => setShowCompare(false)} className="text-gray-400 hover:text-gray-700 text-2xl leading-none">✕</button>
            </div>

            <div className="overflow-y-auto flex-1 p-5 space-y-6">
              {compareLoading ? (
                <div className="py-12 text-center text-gray-400">加载中…</div>
              ) : compareData ? (
                <>
                  {/* 指标对比表格 */}
                  <div>
                    <h3 className="font-semibold text-gray-700 mb-3">关键指标对比</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-gray-500 border-b bg-gray-50">
                            <th className="py-2 px-3">指标</th>
                            {compareData.runs.map(r => (
                              <th key={r.run_id} className="py-2 px-3 text-center min-w-[120px]">
                                <div className="font-semibold text-gray-800 truncate max-w-[120px]" title={r.strategy_id}>
                                  {r.strategy_id}
                                </div>
                                <div className="text-xs text-gray-400 font-mono font-normal">{r.run_id.slice(0, 10)}…</div>
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {([
                            { key: 'sharpe_ratio', label: 'Sharpe Ratio', pct: false, invert: false },
                            { key: 'max_drawdown', label: '最大回撤', pct: true, invert: true },
                            { key: 'total_return', label: '总收益率', pct: true, invert: false },
                            { key: 'calmar_ratio', label: 'Calmar Ratio', pct: false, invert: false },
                            { key: 'sortino_ratio', label: 'Sortino Ratio', pct: false, invert: false },
                            { key: 'annualized_volatility', label: '年化波动率', pct: true, invert: true },
                            { key: 'annualized_return', label: '年化收益', pct: true, invert: false },
                            { key: 'win_rate', label: '胜率', pct: true, invert: false },
                          ] as const).map(({ key, label, pct, invert }) => {
                            const vals = compareData.runs.map(r => {
                              const v = r.metrics?.[key]
                              return v !== undefined && v !== null ? Number(v) : NaN
                            })
                            const validVals = vals.filter(v => !isNaN(v))
                            const best = validVals.length
                              ? invert ? Math.min(...validVals) : Math.max(...validVals)
                              : NaN
                            return (
                              <tr key={key} className="border-b hover:bg-gray-50">
                                <td className="py-2 px-3 text-gray-600">{label}</td>
                                {vals.map((v, i) => {
                                  const isBest = !isNaN(v) && v === best
                                  const display = isNaN(v)
                                    ? '—'
                                    : pct ? `${(v * 100).toFixed(2)}%` : v.toFixed(3)
                                  return (
                                    <td
                                      key={compareData.runs[i].run_id}
                                      className={`py-2 px-3 text-center font-mono ${isBest ? 'text-green-600 font-bold' : 'text-gray-700'}`}
                                    >
                                      {display}
                                    </td>
                                  )
                                })}
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* 净值曲线叠加图 */}
                  {compareData.runs.some(r => r.nav_series.length > 0) && (
                    <div>
                      <h3 className="font-semibold text-gray-700 mb-3">净值曲线叠加</h3>
                      <ResponsiveContainer width="100%" height={280}>
                        <LineChart
                          data={mergeNavSeries(compareData.runs)}
                          margin={{ top: 4, right: 16, left: -20, bottom: 0 }}
                        >
                          <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd"
                            tickFormatter={v => String(v).slice(5)} />
                          <YAxis tick={{ fontSize: 10 }} />
                          <Tooltip formatter={(v: number) => v.toFixed(4)} />
                          <Legend />
                          {compareData.runs.map((r, i) => {
                            const COLORS = ['#3b82f6','#ef4444','#10b981','#f59e0b','#8b5cf6','#06b6d4']
                            return (
                              <Line
                                key={r.run_id}
                                dataKey={r.run_id}
                                name={r.strategy_id}
                                stroke={COLORS[i % COLORS.length]}
                                dot={false}
                                strokeWidth={2}
                                connectNulls
                              />
                            )
                          })}
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* Deploy Wizard Modal */}
      {showDeployWizard && selectedId && detail && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="font-semibold text-gray-900">部署为模拟策略</h2>
              <div className="flex gap-1">
                {[1, 2, 3].map(s => (
                  <span key={s} className={`w-6 h-6 rounded-full text-xs flex items-center justify-center ${
                    s === deployStep ? 'bg-brand-600 text-white' :
                    s < deployStep ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-500'
                  }`}>{s < deployStep ? '✓' : s}</span>
                ))}
              </div>
            </div>

            <div className="p-4">
              {deployStep === 1 && (
                <div className="space-y-3">
                  <h3 className="font-medium text-gray-800">步骤 1：确认回测</h3>
                  <div className="p-3 bg-gray-50 rounded-lg text-sm space-y-1">
                    <div><span className="text-gray-500">策略：</span><strong>{detail.strategy_id}</strong></div>
                    <div><span className="text-gray-500">Run ID：</span><span className="font-mono text-xs">{selectedId.slice(0, 16)}…</span></div>
                    <div><span className="text-gray-500">数据集：</span>{detail.dataset_version}</div>
                    {detail.metrics?.sharpe_ratio != null && (
                      <div><span className="text-gray-500">Sharpe：</span><strong className="text-brand-600">{Number(detail.metrics.sharpe_ratio).toFixed(3)}</strong></div>
                    )}
                  </div>
                </div>
              )}

              {deployStep === 2 && (
                <div className="space-y-3">
                  <h3 className="font-medium text-gray-800">步骤 2：配置资金和风控</h3>
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">初始资金（元）</label>
                    <input type="number" value={deployCash} onChange={e => setDeployCash(e.target.value)}
                      className="input w-full" min={10000} step={10000} />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">风控模式</label>
                    <select value={deployRiskMode} onChange={e => setDeployRiskMode(e.target.value as typeof deployRiskMode)}
                      className="input w-full">
                      <option value="conservative">保守（止损 5%，最大回撤 10%）</option>
                      <option value="moderate">稳健（止损 8%，最大回撤 15%）</option>
                      <option value="aggressive">激进（止损 15%，最大回撤 25%）</option>
                    </select>
                  </div>
                  {/* Risk mode detail */}
                  <div className="p-3 bg-gray-50 rounded-lg text-xs space-y-1 text-gray-600">
                    <div className="font-medium text-gray-700 mb-1">风控参数预览</div>
                    {deployRiskMode === 'conservative' && (
                      <>
                        <div>- 单笔止损：5%（触发后强制平仓）</div>
                        <div>- 最大回撤：10%（触发后暂停策略）</div>
                        <div>- 单股仓位上限：10% NAV</div>
                        <div>- 换手率限制：低频调仓</div>
                      </>
                    )}
                    {deployRiskMode === 'moderate' && (
                      <>
                        <div>- 单笔止损：8%（触发后强制平仓）</div>
                        <div>- 最大回撤：15%（触发后暂停策略）</div>
                        <div>- 单股仓位上限：15% NAV</div>
                        <div>- 换手率限制：中频调仓</div>
                      </>
                    )}
                    {deployRiskMode === 'aggressive' && (
                      <>
                        <div>- 单笔止损：15%（触发后强制平仓）</div>
                        <div>- 最大回撤：25%（触发后暂停策略）</div>
                        <div>- 单股仓位上限：20% NAV</div>
                        <div>- 换手率限制：不限</div>
                      </>
                    )}
                  </div>
                </div>
              )}

              {deployStep === 3 && (
                <div className="space-y-3">
                  <h3 className="font-medium text-gray-800">步骤 3：确认部署</h3>
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm space-y-1">
                    <div>策略：<strong>{detail.strategy_id}</strong></div>
                    <div>初始资金：<strong>¥{Number(deployCash).toLocaleString()}</strong></div>
                    <div>风控模式：<strong>{deployRiskMode}</strong></div>
                  </div>

                  {/* Deployment checklist */}
                  <div className="space-y-2">
                    <label className="flex items-start gap-2 text-xs text-gray-600 cursor-pointer">
                      <input type="checkbox" checked={deployChecklist.confirmBacktest}
                        onChange={e => setDeployChecklist(c => ({ ...c, confirmBacktest: e.target.checked }))}
                        className="mt-0.5 w-4 h-4 rounded border-gray-300 accent-brand-600" />
                      <span>我已确认回测结果满意（Sharpe: {Number(detail.metrics?.sharpe_ratio ?? 0).toFixed(3)}，最大回撤: {((detail.metrics?.max_drawdown ?? 0) * 100).toFixed(1)}%）</span>
                    </label>
                    <label className="flex items-start gap-2 text-xs text-gray-600 cursor-pointer">
                      <input type="checkbox" checked={deployChecklist.understandPaper}
                        onChange={e => setDeployChecklist(c => ({ ...c, understandPaper: e.target.checked }))}
                        className="mt-0.5 w-4 h-4 rounded border-gray-300 accent-brand-600" />
                      <span>我了解这是模拟实盘（Paper Broker），不会执行真实交易</span>
                    </label>
                    <label className="flex items-start gap-2 text-xs text-gray-600 cursor-pointer">
                      <input type="checkbox" checked={deployChecklist.reviewRisk}
                        onChange={e => setDeployChecklist(c => ({ ...c, reviewRisk: e.target.checked }))}
                        className="mt-0.5 w-4 h-4 rounded border-gray-300 accent-brand-600" />
                      <span>我已了解风控规则，策略触发止损/回撤限制后将自动暂停</span>
                    </label>
                  </div>

                  <p className="text-xs text-gray-500">
                    部署后可在"实盘监控"页面查看策略运行状态和执行记录。
                  </p>
                </div>
              )}
            </div>

            <div className="flex justify-between p-4 border-t">
              <button
                onClick={() => {
                  if (deployStep > 1) {
                    setDeployStep(s => s - 1)
                  } else {
                    setShowDeployWizard(false)
                    setDeployStep(1)
                    setDeployCash('1000000')
                    setDeployRiskMode('conservative')
                    setDeployChecklist({ confirmBacktest: false, understandPaper: false, reviewRisk: false })
                  }
                }}
                className="btn-secondary text-sm"
              >
                {deployStep === 1 ? '取消' : '← 上一步'}
              </button>
              {deployStep < 3 ? (
                <button onClick={() => setDeployStep(s => s + 1)} className="btn-primary text-sm">
                  下一步 →
                </button>
              ) : (
                <button
                  onClick={() => deployMutation.mutate({
                    backtest_run_id: selectedId!,
                    initial_cash: Number(deployCash),
                    risk_mode: deployRiskMode,
                  })}
                  disabled={deployMutation.isPending || !deployChecklist.confirmBacktest || !deployChecklist.understandPaper || !deployChecklist.reviewRisk}
                  className="btn-primary text-sm disabled:opacity-40"
                >
                  {deployMutation.isPending ? '部署中…' : '确认部署'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        isOpen={confirmAction !== null}
        title={confirmAction?.type === 'cancel' ? '确认停止回测' : '确认删除回测'}
        message={confirmAction?.type === 'cancel' ? '确定停止此回测？' : '确定删除此回测记录？此操作不可撤销。'}
        confirmLabel={confirmAction?.type === 'cancel' ? '停止' : '删除'}
        variant="danger"
        onConfirm={() => {
          if (confirmAction) {
            if (confirmAction.type === 'cancel') cancelMutation.mutate(confirmAction.runId)
            else deleteMutation.mutate(confirmAction.runId)
          }
          setConfirmAction(null)
        }}
        onCancel={() => setConfirmAction(null)}
      />
    </div>
  )
}

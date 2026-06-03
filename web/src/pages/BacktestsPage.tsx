import { useState, useMemo, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { backtestsApi, backtestExtApi, liveApi } from '@/lib/api'
import { DataTable } from '@/components/ui/DataTable'
import { queryKeys } from '@/lib/queryKeys'
import { toast } from 'sonner'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { PnLChart, type PnLDataPoint } from '@/components/charts/PnLChart'
import {
  BarChart, Bar, LineChart, Line, Legend,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
  Cell, ReferenceLine
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

type Tab = 'overview' | 'tearsheet' | 'overfitting' | 'fills' | 'walkforward' | 'tca' | 'attribution'

/** 将 JSON 对象导出为 .json 文件下载 */
function downloadJson(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/** 将对象数组转为 CSV 并触发下载 */
function downloadCsv(rows: Record<string, unknown>[], filename: string) {
  if (rows.length === 0) return
  const headers = Object.keys(rows[0])
  const lines = [
    headers.join(','),
    ...rows.map(row =>
      headers.map(h => {
        const v = row[h]
        const s = v === null || v === undefined ? '' : String(v)
        return s.includes(',') ? `"${s}"` : s
      }).join(','),
    ),
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function MetricCard({ label, value, sub, warn = false }: {
  label: string; value: string | number; sub?: string; warn?: boolean
}) {
  return (
    <div className={`card text-center py-4 ${warn ? 'border-l-4 border-red-400' : ''}`}>
      <div className={`text-xl font-bold ${warn ? 'text-red-600' : 'text-brand-600'}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  )
}

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
  const initialRunId = searchParams.get('run_id')

  const [selectedId, setSelectedId] = useState<string | null>(initialRunId)
  const [tab, setTab] = useState<Tab>('overview')
  const [page, setPage] = useState(0)
  const pageSize = 20
  const [fillsPage, setFillsPage] = useState(0)
  const fillsPageSize = 50
  const [compareIds, setCompareIds] = useState<string[]>([])
  const [showCompare, setShowCompare] = useState(false)
  const [btSearch, setBtSearch] = useState('')

  const qc = useQueryClient()
  const [showDeployWizard, setShowDeployWizard] = useState(false)
  const [deployStep, setDeployStep] = useState(1)
  const [deployCash, setDeployCash] = useState('1000000')
  const [deployRiskMode, setDeployRiskMode] = useState<'conservative' | 'moderate' | 'aggressive'>('conservative')

  const deployMutation = useMutation({
    mutationFn: liveApi.deploy,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['live', 'deployed'] })
      setShowDeployWizard(false)
      setDeployStep(1)
      toast.success('策略已部署为模拟实盘，前往"实盘监控"查看')
    },
    onError: (e: Error) => toast.error(`部署失败: ${e.message}`),
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
                {['Run ID', '策略', '引擎', '状态', '开始', '结束'].map(h => (
                  <th key={h} className="table-th">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {!filteredBacktests.length && (
                <tr><td colSpan={7} className="table-td text-center text-gray-400 py-8">
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
                    <MetricCard label="配置效应" value={`${Number(attributionData.allocation_effect ?? 0).toFixed(4)}`} />
                    <MetricCard label="选股效应" value={`${Number(attributionData.selection_effect ?? 0).toFixed(4)}`} />
                    <MetricCard label="交互效应" value={`${Number(attributionData.interaction_effect ?? 0).toFixed(4)}`} />
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
                  <p className="text-xs text-gray-500">
                    ⚠ 这是模拟实盘（Paper Broker），不会执行真实交易。
                    部署后可在"实盘监控"页面查看策略运行状态。
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
                  disabled={deployMutation.isPending}
                  className="btn-primary text-sm disabled:opacity-40"
                >
                  {deployMutation.isPending ? '部署中…' : '🚀 确认部署'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

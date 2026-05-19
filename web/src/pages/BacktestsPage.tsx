import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { backtestsApi, backtestExtApi, type BacktestFill } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { useJobPoller } from '@/hooks/useJobPoller'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { PnLChart, type PnLDataPoint } from '@/components/charts/PnLChart'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Cell, ReferenceLine
} from 'recharts'

type Tab = 'overview' | 'tearsheet' | 'overfitting' | 'fills'

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

export function BacktestsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('overview')

  const { data, isLoading, error } = useJobPoller({
    queryKey: queryKeys.backtests.list(50),
    queryFn: () => backtestsApi.list(50),
    isDone: (d) => !d.items.some(r => r.status === 'running' || r.status === 'pending'),
    interval: 5000,
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
    queryKey: ['backtests', selectedId, 'analysis-summary'],
    queryFn: () => backtestsApi.getAnalysis(selectedId!),
    enabled: !!selectedId,
  })

  const { data: fillsData } = useQuery({
    queryKey: queryKeys.backtests.fills(selectedId!),
    queryFn: () => backtestsApi.getFills(selectedId!),
    enabled: !!selectedId && tab === 'fills',
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

  const TABS: { id: Tab; label: string }[] = [
    { id: 'overview', label: '概览' },
    { id: 'tearsheet', label: 'Tearsheet' },
    { id: 'overfitting', label: '过拟合分析' },
    { id: 'fills', label: '交易明细' },
  ]

  if (isLoading) return <p className="text-gray-400">Loading…</p>
  if (error) return <p className="text-red-500">Error: {(error as Error).message}</p>

  return (
    <div>
      <h1 className="page-title">回测评估</h1>
      <p className="page-subtitle">共 {data?.total ?? 0} 条记录 · 点击行选择查看详情</p>

      {/* Run list */}
      <div className="card p-0 overflow-hidden mb-6">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              {['Run ID', '策略', '引擎', '状态', '开始', '结束'].map(h => (
                <th key={h} className="table-th">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!data?.items.length && (
              <tr><td colSpan={6} className="table-td text-center text-gray-400 py-8">暂无回测记录</td></tr>
            )}
            {data?.items.map(r => (
              <tr
                key={r.run_id}
                className={`table-row cursor-pointer ${selectedId === r.run_id ? 'bg-blue-50' : ''}`}
                onClick={() => { setSelectedId(r.run_id); setTab('overview') }}
              >
                <td className="table-td font-mono text-xs">{r.run_id.slice(0, 8)}…</td>
                <td className="table-td font-medium">{r.strategy_id}</td>
                <td className="table-td text-gray-500">{r.engine}</td>
                <td className="table-td"><StatusBadge status={r.status} /></td>
                <td className="table-td text-gray-400">{r.started_at?.slice(0, 16) ?? '—'}</td>
                <td className="table-td text-gray-400">{r.completed_at?.slice(0, 16) ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
              {/* Metrics cards */}
              {detail?.metrics && (
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
                    value={detail.metrics.sharpe_ratio.toFixed(3)}
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

              {!validationData && !multipleTestData && (
                <div className="text-center text-gray-400 py-8">
                  <div className="text-3xl mb-2">🔍</div>
                  <div>需要先运行 <code className="bg-gray-100 px-1 rounded">AnalysisEngine</code> 生成验证数据</div>
                </div>
              )}
            </div>
          )}

          {/* Fills Tab */}
          {tab === 'fills' && (
            <div className="card p-0 overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    {['日期', '资产', '方向', '数量', '价格', '金额', '费用'].map(h => (
                      <th key={h} className="table-th">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {!fillsData?.items.length && (
                    <tr><td colSpan={7} className="table-td text-center text-gray-400 py-8">暂无交易记录</td></tr>
                  )}
                  {(fillsData?.items ?? []).map((f: BacktestFill, i: number) => (
                    <tr key={`${f.trade_date}-${f.asset_id}-${f.side}-${i}`} className="table-row">
                      <td className="table-td text-xs">{String(f.trade_date ?? '').slice(0, 10)}</td>
                      <td className="table-td font-mono text-xs">{f.asset_id}</td>
                      <td className="table-td">
                        <span className={`badge ${f.side === 'buy' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}`}>
                          {f.side === 'buy' ? '买入' : '卖出'}
                        </span>
                      </td>
                      <td className="table-td text-right">{Number(f.qty).toLocaleString()}</td>
                      <td className="table-td text-right">{Number(f.price).toFixed(2)}</td>
                      <td className="table-td text-right">{Number(f.notional).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                      <td className="table-td text-right text-gray-500">{Number(f.total_cost).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

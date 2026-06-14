import { MetricCard } from '../../components/ui/MetricCard'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { backtestsApi, liveApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { toast } from 'sonner'

function marketLabel(m?: string) {
  return { CN: 'A股', US: '美股', HK: '港股' }[m ?? 'CN'] ?? 'A股'
}
function adjLabel(a?: string) {
  return { forward: '前复权', backward: '后复权', none: '不复权' }[a ?? 'forward'] ?? '前复权'
}
function rebalanceLabel(r?: string) {
  return { '1d': '每日', '5d': '每周', '20d': '每月' }[r ?? '1d'] ?? r ?? '每日'
}


import { downloadJson } from '@/lib/download'

export function BacktestOverviewTab() {
  const { id: selectedId } = useParams<{ id: string }>()
  const navigate = useNavigate()
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

  const { data: detail } = useQuery({
    queryKey: queryKeys.backtests.detail(selectedId!),
    queryFn: () => backtestsApi.get(selectedId!),
    enabled: !!selectedId,
  })

  const { data: analysisData } = useQuery({
    queryKey: queryKeys.backtests.analysis(selectedId!),
    queryFn: () => backtestsApi.getAnalysis(selectedId!),
    enabled: !!selectedId,
    staleTime: 60_000,
    retry: false,
  })

  const { data: riskData } = useQuery({
    queryKey: queryKeys.backtests.risk(selectedId!),
    queryFn: () => backtestsApi.getRisk(selectedId!, 20),
    enabled: !!selectedId,
    staleTime: 60_000,
  })

  const analysis = analysisData as Record<string, unknown> | null | undefined
  const overfitScore = Number(analysis?.overall_overfit_score ?? 0)
  const psr = Number(analysis?.psr ?? 0)
  const dsr = Number(analysis?.dsr ?? 0)

  if (!selectedId) return null

  return (
    <div className="space-y-4">
      {/* Export / Deploy buttons */}
      <div className="flex justify-end gap-2">
        <a
          href={`/api/v1/backtests/${selectedId}/export`}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-secondary text-xs flex items-center gap-1"
        >
          Export HTML Report
        </a>
        {detail?.status === 'completed' && (
          <button
            onClick={() => setShowDeployWizard(true)}
            className="btn-primary text-xs flex items-center gap-1"
          >
            Deploy as Paper Strategy
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
            Optimize Factor Weights
          </button>
        )}
      </div>

      {/* Parameter summary */}
      {(() => {
        const ext = detail as unknown as Record<string, unknown> | undefined
        const sc = ext?.strategy_config as Record<string, unknown> | undefined
        if (!sc) return null
        const mr = sc.market_rule as Record<string, unknown> | undefined
        return (
          <div className="text-xs text-gray-400 flex flex-wrap gap-x-3 gap-y-1">
            <span>Market: {marketLabel(mr?.market as string)}</span>
            <span>Adj: {adjLabel(mr?.adj_type as string)}</span>
            <span>Rebalance: {rebalanceLabel(sc.rebalance_frequency as string)}</span>
            <span>Sizer: {String(sc.sizer ?? 'equal_weight')}</span>
          </div>
        )
      })()}

      {/* Metrics cards */}
      {detail?.metrics && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            <MetricCard
              label="Total Return"
              value={`${(detail.metrics.total_return * 100).toFixed(1)}%`}
              warn={detail.metrics.total_return < 0}
            />
            <MetricCard
              label="Annualized Return"
              value={`${(detail.metrics.annualized_return * 100).toFixed(1)}%`}
              warn={detail.metrics.annualized_return < 0}
            />
            <MetricCard
              label="Sharpe"
              value={Number(detail.metrics.sharpe_ratio ?? 0).toFixed(3)}
              warn={detail.metrics.sharpe_ratio < 0}
            />
            <MetricCard
              label="Max Drawdown"
              value={`${(detail.metrics.max_drawdown * 100).toFixed(1)}%`}
              warn={detail.metrics.max_drawdown < -0.2}
            />
            <MetricCard
              label="Win Rate"
              value={`${(detail.metrics.win_rate * 100).toFixed(1)}%`}
            />
            <MetricCard
              label="Total Trades"
              value={String(detail.metrics.total_trades)}
            />
          </div>

          {/* Active management metrics */}
          {(
            detail.metrics.information_ratio != null ||
            detail.metrics.omega_ratio != null ||
            detail.metrics.tail_ratio != null
          ) && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
              <MetricCard
                label="Information Ratio"
                value={detail.metrics.information_ratio != null
                  ? detail.metrics.information_ratio.toFixed(3)
                  : '—'}
                sub="IR (needs benchmark)"
                warn={detail.metrics.information_ratio != null && detail.metrics.information_ratio < 0}
              />
              <MetricCard
                label="Tracking Error"
                value={detail.metrics.tracking_error != null
                  ? `${(detail.metrics.tracking_error * 100).toFixed(2)}%`
                  : '—'}
                sub="TE (annualized)"
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
                label="Turnover"
                value={detail.metrics.turnover_pct != null
                  ? `${(detail.metrics.turnover_pct * 100).toFixed(1)}%`
                  : '—'}
                sub="Avg single-side"
              />
            </div>
          )}

          {/* Export metrics button */}
          <div className="flex justify-end">
            <button
              className="btn-secondary text-sm"
              onClick={() => downloadJson(
                detail.metrics,
                `metrics_${selectedId?.slice(0, 8) ?? 'backtest'}.json`,
              )}
            >
              Export Metrics JSON
            </button>
          </div>
        </>
      )}

      {/* Risk snapshot */}
      {riskData?.items?.[0] && (
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Latest Risk Snapshot</h3>
          <div className="grid grid-cols-4 gap-4">
            <MetricCard label="Drawdown" value={`${((riskData.items[0].drawdown as number ?? 0) * 100).toFixed(2)}%`} warn />
            <MetricCard label="Leverage" value={(riskData.items[0].gross_leverage as number ?? 0).toFixed(2)} />
            <MetricCard label="VaR 95%" value={`${((riskData.items[0].var_95 as number ?? 0) * 100).toFixed(2)}%`} />
            <MetricCard label="Beta" value={(riskData.items[0].beta as number ?? 0).toFixed(2)} />
          </div>
        </div>
      )}

      {/* Analysis summary */}
      {analysis && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <MetricCard label="PSR" value={psr.toFixed(3)} sub="Probabilistic Sharpe" warn={psr < 0.5} />
            <MetricCard label="DSR" value={dsr.toFixed(3)} sub="Deflated Sharpe" warn={dsr < 0.5} />
            <MetricCard label="Summary" value={String(analysis.summary ?? '').slice(0, 60) || '—'} sub="" />
            <MetricCard label="Overfit Risk" value={`${Math.round(overfitScore * 100)}%`} warn={overfitScore > 0.5} />
          </div>
          <div className="card text-sm text-gray-700">
            <div className="font-medium mb-1">Analysis Summary</div>
            <p className="text-gray-600">{String(analysis.summary ?? 'No analysis summary available')}</p>
          </div>
        </div>
      )}

      {!detail?.metrics && !analysis && (
        <div className="card text-center text-gray-400 py-12">
          <div className="text-4xl mb-3">Chart</div>
          <div>Select a completed backtest to view details</div>
        </div>
      )}

      {/* Deploy Wizard Modal */}
      {showDeployWizard && selectedId && detail && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="font-semibold text-gray-900">Deploy as Paper Strategy</h2>
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
                  <h3 className="font-medium text-gray-800">Step 1: Confirm Backtest</h3>
                  <div className="p-3 bg-gray-50 rounded-lg text-sm space-y-1">
                    <div><span className="text-gray-500">Strategy: </span><strong>{detail.strategy_id}</strong></div>
                    <div><span className="text-gray-500">Run ID: </span><span className="font-mono text-xs">{selectedId.slice(0, 16)}...</span></div>
                    <div><span className="text-gray-500">Dataset: </span>{detail.dataset_version}</div>
                    {detail.metrics?.sharpe_ratio != null && (
                      <div><span className="text-gray-500">Sharpe: </span><strong className="text-brand-600">{Number(detail.metrics.sharpe_ratio).toFixed(3)}</strong></div>
                    )}
                  </div>
                </div>
              )}

              {deployStep === 2 && (
                <div className="space-y-3">
                  <h3 className="font-medium text-gray-800">Step 2: Configure Capital & Risk</h3>
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">Initial Capital</label>
                    <input type="number" value={deployCash} onChange={e => setDeployCash(e.target.value)}
                      className="input w-full" min={10000} step={10000} />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">Risk Mode</label>
                    <select value={deployRiskMode} onChange={e => setDeployRiskMode(e.target.value as typeof deployRiskMode)}
                      className="input w-full">
                      <option value="conservative">Conservative (stop-loss 5%, max DD 10%)</option>
                      <option value="moderate">Moderate (stop-loss 8%, max DD 15%)</option>
                      <option value="aggressive">Aggressive (stop-loss 15%, max DD 25%)</option>
                    </select>
                  </div>
                  <div className="p-3 bg-gray-50 rounded-lg text-xs space-y-1 text-gray-600">
                    <div className="font-medium text-gray-700 mb-1">Risk Parameters Preview</div>
                    {deployRiskMode === 'conservative' && (
                      <>
                        <div>- Per-trade stop-loss: 5%</div>
                        <div>- Max drawdown: 10% (pauses strategy)</div>
                        <div>- Single stock limit: 10% NAV</div>
                      </>
                    )}
                    {deployRiskMode === 'moderate' && (
                      <>
                        <div>- Per-trade stop-loss: 8%</div>
                        <div>- Max drawdown: 15% (pauses strategy)</div>
                        <div>- Single stock limit: 15% NAV</div>
                      </>
                    )}
                    {deployRiskMode === 'aggressive' && (
                      <>
                        <div>- Per-trade stop-loss: 15%</div>
                        <div>- Max drawdown: 25% (pauses strategy)</div>
                        <div>- Single stock limit: 20% NAV</div>
                      </>
                    )}
                  </div>
                </div>
              )}

              {deployStep === 3 && (
                <div className="space-y-3">
                  <h3 className="font-medium text-gray-800">Step 3: Confirm Deployment</h3>
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm space-y-1">
                    <div>Strategy: <strong>{detail.strategy_id}</strong></div>
                    <div>Initial Capital: <strong>{Number(deployCash).toLocaleString()}</strong></div>
                    <div>Risk Mode: <strong>{deployRiskMode}</strong></div>
                  </div>

                  <div className="space-y-2">
                    <label className="flex items-start gap-2 text-xs text-gray-600 cursor-pointer">
                      <input type="checkbox" checked={deployChecklist.confirmBacktest}
                        onChange={e => setDeployChecklist(c => ({ ...c, confirmBacktest: e.target.checked }))}
                        className="mt-0.5 w-4 h-4 rounded border-gray-300 accent-brand-600" />
                      <span>I confirm backtest results are satisfactory (Sharpe: {Number(detail.metrics?.sharpe_ratio ?? 0).toFixed(3)}, Max DD: {((detail.metrics?.max_drawdown ?? 0) * 100).toFixed(1)}%)</span>
                    </label>
                    <label className="flex items-start gap-2 text-xs text-gray-600 cursor-pointer">
                      <input type="checkbox" checked={deployChecklist.understandPaper}
                        onChange={e => setDeployChecklist(c => ({ ...c, understandPaper: e.target.checked }))}
                        className="mt-0.5 w-4 h-4 rounded border-gray-300 accent-brand-600" />
                      <span>I understand this is a Paper Trading simulation, not real execution</span>
                    </label>
                    <label className="flex items-start gap-2 text-xs text-gray-600 cursor-pointer">
                      <input type="checkbox" checked={deployChecklist.reviewRisk}
                        onChange={e => setDeployChecklist(c => ({ ...c, reviewRisk: e.target.checked }))}
                        className="mt-0.5 w-4 h-4 rounded border-gray-300 accent-brand-600" />
                      <span>I understand the risk rules; strategy will auto-pause on stop-loss/drawdown triggers</span>
                    </label>
                  </div>

                  <p className="text-xs text-gray-500">
                    After deployment, view strategy status and execution records in the "Live Monitor" page.
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
                {deployStep === 1 ? 'Cancel' : 'Back'}
              </button>
              {deployStep < 3 ? (
                <button onClick={() => setDeployStep(s => s + 1)} className="btn-primary text-sm">
                  Next
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
                  {deployMutation.isPending ? 'Deploying...' : 'Confirm Deployment'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

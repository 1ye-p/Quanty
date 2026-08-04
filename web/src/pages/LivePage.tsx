import { useState, useMemo, useCallback } from 'react'
import { useTranslation, Trans } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tradingApi, liveApi, type RealtimeQuote } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { useRealtimeQuote } from '@/hooks/useRealtimeQuote'
import { OrderForm } from '@/components/trading/OrderForm'
import { PositionTable } from '@/components/trading/PositionTable'
import { OrderBook } from '@/components/trading/OrderBook'
import { PositionConcentration, type ConcentrationSnapshot } from '@/components/charts/PositionConcentration'
import { DeploymentCard } from '@/components/live/DeploymentCard'
import { FundCurve } from '@/components/live/FundCurve'
import { PositionPnL } from '@/components/live/PositionPnL'
import { ExecutionLog } from '@/components/live/ExecutionLog'
import { RiskMonitor } from '@/components/live/RiskMonitor'
import { toast } from 'sonner'

type LiveTab = 'overview' | 'positions' | 'executions' | 'risk'

const TAB_LABEL_KEYS: Record<LiveTab, string> = {
  overview: 'page.live.tab.overview',
  positions: 'page.live.tab.positions',
  executions: 'page.live.tab.executions',
  risk: 'page.live.tab.risk',
}

export function LivePage() {
  const { t } = useTranslation()
  const [selectedSymbol, setSelectedSymbol] = useState<string>('')
  const [selectedLiveId, setSelectedLiveId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<LiveTab>('overview')
  const [broker] = useState('paper')

  const qc = useQueryClient()

  const [stoppingId, setStoppingId] = useState<string | null>(null)
  const stopMutation = useMutation({
    mutationFn: (liveId: string) => {
      setStoppingId(liveId)
      return liveApi.stopDeployed(liveId)
    },
    onSuccess: () => {
      setStoppingId(null)
      qc.invalidateQueries({ queryKey: ['live', 'deployed'] })
      toast.success(t('page.live.kill_switch.stop_success'))
    },
    onError: (e: Error) => {
      setStoppingId(null)
      qc.invalidateQueries({ queryKey: ['live', 'deployed'] })
      toast.error(t('page.live.kill_switch.stop_failed', { message: e.message }))
    },
  })

  // ── Kill-Switch ───────────────────────────────────────────────────────────

  const [killDialogOpen, setKillDialogOpen] = useState(false)
  const [resumeDialogOpen, setResumeDialogOpen] = useState(false)
  const [cancelOrders, setCancelOrders] = useState(true)
  const [closePositions, setClosePositions] = useState(false)
  const [confirmText, setConfirmText] = useState('')

  const { data: ksStatus, refetch: refetchKs } = useQuery({
    queryKey: ['live', 'kill-switch', 'status'],
    queryFn: liveApi.getKillSwitchStatus,
    refetchInterval: 10_000,
    staleTime: 10_000,
  })

  const killSwitchActive = ksStatus?.active ?? false

  const killMutation = useMutation({
    mutationFn: () =>
      liveApi.activateKillSwitch({ cancel_orders: cancelOrders, close_positions: closePositions }),
    onSuccess: (res) => {
      setKillDialogOpen(false)
      setConfirmText('')
      const r = res.results
      toast.success(
        t('page.live.kill_switch.activated_toast', {
          strategies: r.strategies_stopped,
          orders: r.orders_cancelled,
          positions: r.positions_closed,
        }),
        { duration: 6000 },
      )
      refetchKs()
      qc.invalidateQueries({ queryKey: ['live', 'deployed'] })
    },
    onError: (e: Error) => {
      toast.error(t('page.live.kill_switch.activate_failed', { message: e.message }))
    },
  })

  const resumeMutation = useMutation({
    mutationFn: liveApi.resumeStrategies,
    onSuccess: (res) => {
      setResumeDialogOpen(false)
      toast.success(t('page.live.resume.success_toast', { count: res.strategies_restored }))
      refetchKs()
      qc.invalidateQueries({ queryKey: ['live', 'deployed'] })
    },
    onError: (e: Error) => {
      toast.error(t('page.live.resume.failed', { message: e.message }))
    },
  })

  const handleKillSwitchClick = useCallback(() => {
    setConfirmText('')
    setCancelOrders(true)
    setClosePositions(false)
    setKillDialogOpen(true)
  }, [])

  const handleResumeClick = useCallback(() => {
    setResumeDialogOpen(true)
  }, [])

  // Account data
  const { data: account } = useQuery({
    queryKey: extendedQueryKeys.trading.account(broker),
    queryFn: () => tradingApi.account(broker),
    refetchInterval: 5000,
  })

  // PnL data
  const { data: pnlData } = useQuery({
    queryKey: extendedQueryKeys.trading.pnl(broker),
    queryFn: () => tradingApi.pnl(broker),
    refetchInterval: 5000,
  })

  // Positions for quote tracking
  const { data: positions } = useQuery({
    queryKey: extendedQueryKeys.trading.positions(broker),
    queryFn: () => tradingApi.positions(broker),
  })

  // Deployed strategies (30s refresh)
  const { data: deployed } = useQuery({
    queryKey: ['live', 'deployed'],
    queryFn: liveApi.deployed,
    refetchInterval: 30_000,
    staleTime: 30_000,
  })

  // Real-time quotes for held positions
  const symbols = positions?.items.map(p => p.asset_id.split(':')[1]) ?? []
  const { quotes, connected } = useRealtimeQuote({
    symbols,
    interval: 5,
    enabled: symbols.length > 0,
  })

  // Selected symbol quote
  const selectedQuote = selectedSymbol ? quotes[selectedSymbol] : null

  // Selected deployment
  const selectedDeployment = deployed?.items?.find(d => d.live_id === selectedLiveId) ?? null

  // Compute position concentration from current positions
  const concentrationData = useMemo((): ConcentrationSnapshot[] => {
    if (!positions?.items || positions.items.length === 0) return []

    const totalValue = positions.items.reduce((sum, p) => {
      const ticker = p.asset_id.includes(':') ? p.asset_id.split(':')[1] : p.asset_id
      const price = quotes[ticker]?.price ?? p.avg_cost
      return sum + (p.qty * price)
    }, 0) + (account?.cash ?? 0)

    if (totalValue <= 0) return []

    const sortedPositions = [...positions.items]
      .map(p => {
        const ticker = p.asset_id.includes(':') ? p.asset_id.split(':')[1] : p.asset_id
        const price = quotes[ticker]?.price ?? p.avg_cost
        return {
          ...p,
          value: p.qty * price,
          weight: (p.qty * price) / totalValue,
        }
      })
      .sort((a, b) => b.weight - a.weight)

    const top5Weight = sortedPositions.slice(0, 5).reduce((sum, p) => sum + p.weight, 0)
    const top10Weight = sortedPositions.slice(0, 10).reduce((sum, p) => sum + p.weight, 0)
    const top20Weight = sortedPositions.slice(0, 20).reduce((sum, p) => sum + p.weight, 0)
    const hhi = sortedPositions.reduce((sum, p) => sum + Math.pow(p.weight * 100, 2), 0)
    const today = new Date().toISOString().slice(0, 10)

    return [{
      date: today,
      top5_weight: top5Weight,
      top10_weight: top10Weight,
      top20_weight: top20Weight,
      hhi,
    }]
  }, [positions, quotes, account])

  return (
    <div className="space-y-6">
      {/* Kill-Switch Warning Banner */}
      {killSwitchActive && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-lg border bg-red-50 border-red-200 text-red-800">
          <span className="text-lg">&#9888;</span>
          <span className="font-medium">{t('page.live.kill_switch.active_banner')}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title">{t('page.live.title')}</h1>
          <p className="page-subtitle">{t('page.live.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Kill-Switch / Resume Button */}
          {killSwitchActive ? (
            <button
              onClick={handleResumeClick}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-white bg-green-600 hover:bg-green-700 transition-colors"
            >
              {t('page.live.btn.resume')}
            </button>
          ) : (
            <button
              onClick={handleKillSwitchClick}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-white bg-red-600 hover:bg-red-700 transition-colors"
            >
              {t('page.live.btn.kill_switch')}
            </button>
          )}
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm text-gray-500">{t(connected ? 'page.live.conn.connected' : 'page.live.conn.disconnected')}</span>
        </div>
      </div>

      {/* Kill-Switch Confirmation Dialog */}
      {killDialogOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setKillDialogOpen(false)}
        >
          <div
            className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-red-700">{t('page.live.kill_switch.dialog_title')}</h3>
            <p className="mt-2 text-sm text-gray-600">
              {t('page.live.kill_switch.dialog_desc')}
            </p>

            <div className="mt-4 space-y-3">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={cancelOrders}
                  onChange={(e) => setCancelOrders(e.target.checked)}
                  className="rounded border-gray-300"
                />
                {t('page.live.kill_switch.cancel_orders')}
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={closePositions}
                  onChange={(e) => setClosePositions(e.target.checked)}
                  className="rounded border-gray-300"
                />
                {t('page.live.kill_switch.close_positions')}
              </label>

              <div className="pt-2">
                <label className="block text-sm text-gray-600 mb-1">
                  <Trans
                    i18nKey="page.live.kill_switch.confirm_label"
                    components={{ b: <span className="font-mono font-bold" /> }}
                  />
                </label>
                <input
                  type="text"
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  placeholder="STOP"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
                  autoFocus
                />
              </div>
            </div>

            <div className="mt-5 flex gap-3 justify-end">
              <button
                onClick={() => setKillDialogOpen(false)}
                className="btn-secondary text-sm"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={() => killMutation.mutate()}
                disabled={confirmText !== 'STOP' || killMutation.isPending}
                className={`px-4 py-2 rounded-lg text-sm font-semibold text-white transition-colors ${
                  confirmText === 'STOP'
                    ? 'bg-red-600 hover:bg-red-700'
                    : 'bg-gray-300 cursor-not-allowed'
                }`}
              >
                {killMutation.isPending ? t('page.live.kill_switch.executing') : t('page.live.kill_switch.confirm_button')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Resume Confirmation Dialog */}
      {resumeDialogOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setResumeDialogOpen(false)}
        >
          <div
            className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-gray-900">{t('page.live.resume.dialog_title')}</h3>
            <p className="mt-2 text-sm text-gray-600">
              {t('page.live.resume.dialog_desc')}
            </p>
            <div className="mt-5 flex gap-3 justify-end">
              <button
                onClick={() => setResumeDialogOpen(false)}
                className="btn-secondary text-sm"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={() => resumeMutation.mutate(undefined)}
                disabled={resumeMutation.isPending}
                className="px-4 py-2 rounded-lg text-sm font-semibold text-white bg-green-600 hover:bg-green-700 transition-colors disabled:bg-gray-300"
              >
                {resumeMutation.isPending ? t('page.live.resume.executing') : t('page.live.resume.confirm_button')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Deployed Strategies Grid */}
      {deployed?.items && deployed.items.length > 0 && (
        <div>
          <h2 className="font-semibold text-gray-800 mb-3">
            {t('page.live.section.deployed_title', {
              active: deployed.items.filter(d => d.status === 'active').length,
            })}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {deployed.items.map(d => (
              <DeploymentCard
                key={d.live_id}
                deployment={d}
                selected={selectedLiveId === d.live_id}
                onSelect={() => {
                  setSelectedLiveId(selectedLiveId === d.live_id ? null : d.live_id)
                  setActiveTab('overview')
                }}
                onStop={() => stopMutation.mutate(d.live_id)}
                stopPending={stoppingId === d.live_id}
              />
            ))}
          </div>
        </div>
      )}

      {/* Tab Navigation for Selected Deployment */}
      {selectedLiveId && (
        <div className="card">
          <div className="flex items-center gap-1 border-b border-gray-200 mb-4">
            {(Object.keys(TAB_LABEL_KEYS) as LiveTab[]).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                  activeTab === tab
                    ? 'border-brand-500 text-brand-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {t(TAB_LABEL_KEYS[tab])}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          {activeTab === 'overview' && (
            <div className="space-y-4">
              {selectedDeployment && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="text-center p-3 bg-gray-50 rounded-lg">
                    <div className="text-lg font-bold text-brand-600">
                      ¥{selectedDeployment.initial_cash?.toLocaleString()}
                    </div>
                    <div className="text-xs text-gray-500">{t('page.live.stat.initial_cash')}</div>
                  </div>
                  <div className="text-center p-3 bg-gray-50 rounded-lg">
                    <div className="text-lg font-bold">
                      {selectedDeployment.risk_mode}
                    </div>
                    <div className="text-xs text-gray-500">{t('page.live.stat.risk_mode')}</div>
                  </div>
                  <div className="text-center p-3 bg-gray-50 rounded-lg">
                    <div className="text-lg font-bold">
                      {selectedDeployment.metrics?.sharpe != null
                        ? Number(selectedDeployment.metrics.sharpe).toFixed(3)
                        : '--'}
                    </div>
                    <div className="text-xs text-gray-500">{t('page.live.stat.sharpe')}</div>
                  </div>
                  <div className="text-center p-3 bg-gray-50 rounded-lg">
                    <div className={`text-lg font-bold ${
                      (selectedDeployment.metrics?.cagr ?? 0) >= 0 ? 'text-red-600' : 'text-green-600'
                    }`}>
                      {selectedDeployment.metrics?.cagr != null
                        ? `${(Number(selectedDeployment.metrics.cagr) * 100).toFixed(2)}%`
                        : '--'}
                    </div>
                    <div className="text-xs text-gray-500">{t('page.live.stat.return_rate')}</div>
                  </div>
                </div>
              )}
              <FundCurve deploymentId={selectedLiveId} />
            </div>
          )}

          {activeTab === 'positions' && (
            <PositionPnL deploymentId={selectedLiveId} />
          )}

          {activeTab === 'executions' && (
            <ExecutionLog deploymentId={selectedLiveId} />
          )}

          {activeTab === 'risk' && (
            <RiskMonitor deploymentId={selectedLiveId} />
          )}
        </div>
      )}

      {/* Account Overview */}
      {account && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="card text-center">
            <div className="text-xl font-bold text-brand-600">
              {account.nav.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
            <div className="text-xs text-gray-500 mt-1">{t('page.live.stat.nav')}</div>
          </div>
          <div className="card text-center">
            <div className="text-xl font-bold">
              {account.cash.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
            <div className="text-xs text-gray-500 mt-1">{t('page.live.stat.cash')}</div>
          </div>
          <div className="card text-center">
            <div className={`text-xl font-bold ${(pnlData?.total_pnl ?? 0) >= 0 ? 'text-red-600' : 'text-green-600'}`}>
              {pnlData ? `${pnlData.total_pnl >= 0 ? '+' : ''}${pnlData.total_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '--'}
            </div>
            <div className="text-xs text-gray-500 mt-1">{t('page.live.stat.total_pnl')}</div>
          </div>
          <div className="card text-center">
            <div className={`text-xl font-bold ${(pnlData?.return_pct ?? 0) >= 0 ? 'text-red-600' : 'text-green-600'}`}>
              {pnlData ? `${pnlData.return_pct >= 0 ? '+' : ''}${pnlData.return_pct.toFixed(2)}%` : '--'}
            </div>
            <div className="text-xs text-gray-500 mt-1">{t('page.live.stat.return_rate')}</div>
          </div>
        </div>
      )}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Positions + Orders */}
        <div className="lg:col-span-2 space-y-6">
          {/* Position Concentration Chart */}
          {concentrationData.length > 0 && (
            <PositionConcentration data={concentrationData} title={t('page.live.section.position_concentration')} />
          )}

          {/* Real-time Quotes for Positions */}
          {symbols.length > 0 && Object.keys(quotes).length > 0 && (
            <div className="card">
              <h2 className="font-semibold text-gray-800 mb-4">{t('page.live.section.realtime_quotes')}</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="pb-2 pr-4">{t('page.live.quote.symbol')}</th>
                      <th className="pb-2 pr-4 text-right">{t('page.live.quote.price')}</th>
                      <th className="pb-2 pr-4 text-right">{t('page.live.quote.change')}</th>
                      <th className="pb-2 pr-4 text-right">{t('page.live.quote.change_pct')}</th>
                      <th className="pb-2 pr-4 text-right">{t('page.live.quote.volume')}</th>
                      <th className="pb-2 text-right">{t('page.live.quote.bid_ask')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(quotes).map(([symbol, q]: [string, RealtimeQuote]) => (
                      <tr
                        key={symbol}
                        className={`border-b last:border-0 cursor-pointer hover:bg-gray-50 ${
                          selectedSymbol === symbol ? 'bg-blue-50' : ''
                        }`}
                        onClick={() => setSelectedSymbol(symbol)}
                      >
                        <td className="py-2 pr-4 font-mono">{symbol}</td>
                        <td className="py-2 pr-4 text-right font-medium">{q.price.toFixed(2)}</td>
                        <td className={`py-2 pr-4 text-right ${q.change >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                          {q.change >= 0 ? '+' : ''}{q.change.toFixed(2)}
                        </td>
                        <td className={`py-2 pr-4 text-right ${q.change_pct >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                          {q.change_pct >= 0 ? '+' : ''}{q.change_pct.toFixed(2)}%
                        </td>
                        <td className="py-2 pr-4 text-right">{(q.volume / 10000).toFixed(0)}{t('page.live.quote.volume_unit')}</td>
                        <td className="py-2 text-right text-xs">
                          <span className="text-red-600">{q.bid1.toFixed(2)}</span>
                          {' / '}
                          <span className="text-green-600">{q.ask1.toFixed(2)}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Positions */}
          <PositionTable broker={broker} />

          {/* Orders */}
          <OrderBook broker={broker} />
        </div>

        {/* Right: Order Form + Detail */}
        <div className="space-y-6">
          {/* Order Form */}
          <OrderForm broker={broker} />

          {/* Selected Symbol Detail */}
          {selectedQuote && (
            <div className="card">
              <h2 className="font-semibold text-gray-800 mb-4">
                {t('page.live.section.quote_detail', { symbol: selectedSymbol })}
              </h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">{t('page.live.quote.open')}</span>
                  <span>{selectedQuote.open.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">{t('page.live.quote.high')}</span>
                  <span className="text-red-600">{selectedQuote.high.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">{t('page.live.quote.low')}</span>
                  <span className="text-green-600">{selectedQuote.low.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">{t('page.live.quote.prev_close')}</span>
                  <span>{selectedQuote.prev_close.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">{t('page.live.quote.volume')}</span>
                  <span>{(selectedQuote.volume / 10000).toFixed(0)}{t('page.live.quote.volume_unit_lot')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">{t('page.live.quote.amount')}</span>
                  <span>{(selectedQuote.amount / 100000000).toFixed(2)}{t('page.live.quote.amount_unit')}</span>
                </div>
                <hr />
                <div className="flex justify-between">
                  <span className="text-gray-500">{t('page.live.quote.bid1')}</span>
                  <span className="text-red-600">
                    {selectedQuote.bid1.toFixed(2)} x {selectedQuote.bid1_vol}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">{t('page.live.quote.ask1')}</span>
                  <span className="text-green-600">
                    {selectedQuote.ask1.toFixed(2)} x {selectedQuote.ask1_vol}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Account Detail */}
          {account && (
            <div className="card">
              <h2 className="font-semibold text-gray-800 mb-4">{t('page.live.section.account_detail')}</h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">{t('page.live.stat.market_value')}</span>
                  <span>{(account.nav - account.cash).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">{t('page.live.stat.gross_exposure')}</span>
                  <span>{account.gross_exposure.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">{t('page.live.stat.net_exposure')}</span>
                  <span>{account.net_exposure.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">{t('page.live.stat.realized_pnl')}</span>
                  <span className={account.realized_pnl >= 0 ? 'text-red-600' : 'text-green-600'}>
                    {account.realized_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">{t('page.live.stat.unrealized_pnl')}</span>
                  <span className={account.unrealized_pnl >= 0 ? 'text-red-600' : 'text-green-600'}>
                    {account.unrealized_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

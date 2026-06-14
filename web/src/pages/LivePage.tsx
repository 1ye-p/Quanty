import { useState, useMemo } from 'react'
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

const TAB_LABELS: Record<LiveTab, string> = {
  overview: '总览',
  positions: '持仓',
  executions: '执行日志',
  risk: '风险监控',
}

export function LivePage() {
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
      toast.success('策略已停止')
    },
    onError: (e: Error) => {
      setStoppingId(null)
      qc.invalidateQueries({ queryKey: ['live', 'deployed'] })
      toast.error(`停止失败: ${e.message}`)
    },
  })

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
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title">实盘监控</h1>
          <p className="page-subtitle">实时行情 · 持仓管理 · 订单交易</p>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm text-gray-500">{connected ? '已连接' : '未连接'}</span>
        </div>
      </div>

      {/* Deployed Strategies Grid */}
      {deployed?.items && deployed.items.length > 0 && (
        <div>
          <h2 className="font-semibold text-gray-800 mb-3">
            模拟策略（{deployed.items.filter(d => d.status === 'active').length} 个激活中）
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
            {(Object.keys(TAB_LABELS) as LiveTab[]).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                  activeTab === tab
                    ? 'border-brand-500 text-brand-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {TAB_LABELS[tab]}
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
                    <div className="text-xs text-gray-500">初始资金</div>
                  </div>
                  <div className="text-center p-3 bg-gray-50 rounded-lg">
                    <div className="text-lg font-bold">
                      {selectedDeployment.risk_mode}
                    </div>
                    <div className="text-xs text-gray-500">风控模式</div>
                  </div>
                  <div className="text-center p-3 bg-gray-50 rounded-lg">
                    <div className="text-lg font-bold">
                      {selectedDeployment.metrics?.sharpe != null
                        ? Number(selectedDeployment.metrics.sharpe).toFixed(3)
                        : '--'}
                    </div>
                    <div className="text-xs text-gray-500">Sharpe</div>
                  </div>
                  <div className="text-center p-3 bg-gray-50 rounded-lg">
                    <div className={`text-lg font-bold ${
                      (selectedDeployment.metrics?.cagr ?? 0) >= 0 ? 'text-red-600' : 'text-green-600'
                    }`}>
                      {selectedDeployment.metrics?.cagr != null
                        ? `${(Number(selectedDeployment.metrics.cagr) * 100).toFixed(2)}%`
                        : '--'}
                    </div>
                    <div className="text-xs text-gray-500">收益率</div>
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
            <div className="text-xs text-gray-500 mt-1">NAV</div>
          </div>
          <div className="card text-center">
            <div className="text-xl font-bold">
              {account.cash.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
            <div className="text-xs text-gray-500 mt-1">可用资金</div>
          </div>
          <div className="card text-center">
            <div className={`text-xl font-bold ${(pnlData?.total_pnl ?? 0) >= 0 ? 'text-red-600' : 'text-green-600'}`}>
              {pnlData ? `${pnlData.total_pnl >= 0 ? '+' : ''}${pnlData.total_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '--'}
            </div>
            <div className="text-xs text-gray-500 mt-1">总盈亏</div>
          </div>
          <div className="card text-center">
            <div className={`text-xl font-bold ${(pnlData?.return_pct ?? 0) >= 0 ? 'text-red-600' : 'text-green-600'}`}>
              {pnlData ? `${pnlData.return_pct >= 0 ? '+' : ''}${pnlData.return_pct.toFixed(2)}%` : '--'}
            </div>
            <div className="text-xs text-gray-500 mt-1">收益率</div>
          </div>
        </div>
      )}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Positions + Orders */}
        <div className="lg:col-span-2 space-y-6">
          {/* Position Concentration Chart */}
          {concentrationData.length > 0 && (
            <PositionConcentration data={concentrationData} title="持仓集中度" />
          )}

          {/* Real-time Quotes for Positions */}
          {symbols.length > 0 && Object.keys(quotes).length > 0 && (
            <div className="card">
              <h2 className="font-semibold text-gray-800 mb-4">实时行情</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="pb-2 pr-4">代码</th>
                      <th className="pb-2 pr-4 text-right">最新价</th>
                      <th className="pb-2 pr-4 text-right">涨跌额</th>
                      <th className="pb-2 pr-4 text-right">涨跌幅</th>
                      <th className="pb-2 pr-4 text-right">成交量</th>
                      <th className="pb-2 text-right">买一/卖一</th>
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
                        <td className="py-2 pr-4 text-right">{(q.volume / 10000).toFixed(0)}万</td>
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
                {selectedSymbol} 行情详情
              </h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">开盘</span>
                  <span>{selectedQuote.open.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">最高</span>
                  <span className="text-red-600">{selectedQuote.high.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">最低</span>
                  <span className="text-green-600">{selectedQuote.low.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">昨收</span>
                  <span>{selectedQuote.prev_close.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">成交量</span>
                  <span>{(selectedQuote.volume / 10000).toFixed(0)}万手</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">成交额</span>
                  <span>{(selectedQuote.amount / 100000000).toFixed(2)}亿</span>
                </div>
                <hr />
                <div className="flex justify-between">
                  <span className="text-gray-500">买一</span>
                  <span className="text-red-600">
                    {selectedQuote.bid1.toFixed(2)} x {selectedQuote.bid1_vol}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">卖一</span>
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
              <h2 className="font-semibold text-gray-800 mb-4">账户详情</h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">总市值</span>
                  <span>{(account.nav - account.cash).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">总敞口</span>
                  <span>{account.gross_exposure.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">净敞口</span>
                  <span>{account.net_exposure.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">已实现盈亏</span>
                  <span className={account.realized_pnl >= 0 ? 'text-red-600' : 'text-green-600'}>
                    {account.realized_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">未实现盈亏</span>
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

import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tradingApi, liveApi, type RealtimeQuote, type LiveExecution } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { useRealtimeQuote } from '@/hooks/useRealtimeQuote'
import { OrderForm } from '@/components/trading/OrderForm'
import { PositionTable } from '@/components/trading/PositionTable'
import { OrderBook } from '@/components/trading/OrderBook'
import { PositionConcentration, type ConcentrationSnapshot } from '@/components/charts/PositionConcentration'
import { toast } from 'sonner'

export function LivePage() {
  const [selectedSymbol, setSelectedSymbol] = useState<string>('')
  const [selectedLiveId, setSelectedLiveId] = useState<string | null>(null)
  const [broker] = useState('paper')

  const qc = useQueryClient()

  const stopMutation = useMutation({
    mutationFn: (liveId: string) => liveApi.stopDeployed(liveId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['live', 'deployed'] })
      toast.success('策略已停止')
    },
    onError: (e: Error) => {
      // Refresh list on any error — 409 means already stopped on server,
      // so the local status may be stale
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

  // Deployed strategies
  const { data: deployed } = useQuery({
    queryKey: ['live', 'deployed'],
    queryFn: liveApi.deployed,
    staleTime: 30_000,
  })

  // Execution history for selected live strategy
  const { data: executions } = useQuery({
    queryKey: ['live', 'executions', selectedLiveId],
    queryFn: () => liveApi.getExecutions(selectedLiveId!, 20),
    enabled: !!selectedLiveId,
    staleTime: 10_000,
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

  // Compute position concentration from current positions
  const concentrationData = useMemo((): ConcentrationSnapshot[] => {
    if (!positions?.items || positions.items.length === 0) return []

    // Compute total NAV from positions
    const totalValue = positions.items.reduce((sum, p) => {
      const ticker = p.asset_id.includes(':') ? p.asset_id.split(':')[1] : p.asset_id
      const price = quotes[ticker]?.price ?? p.avg_cost
      return sum + (p.qty * price)
    }, 0) + (account?.cash ?? 0)

    if (totalValue <= 0) return []

    // Sort positions by value descending
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

    // Compute top-N weights
    const top5Weight = sortedPositions.slice(0, 5).reduce((sum, p) => sum + p.weight, 0)
    const top10Weight = sortedPositions.slice(0, 10).reduce((sum, p) => sum + p.weight, 0)
    const top20Weight = sortedPositions.slice(0, 20).reduce((sum, p) => sum + p.weight, 0)

    // Compute HHI (Herfindahl-Hirschman Index)
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

      {/* 已部署的模拟策略 */}
      {deployed?.items && deployed.items.length > 0 && (
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-3">
            模拟策略（{deployed.items.filter(d => d.status === 'active').length} 个激活中）
          </h2>
          <div className="space-y-3">
            {deployed.items.map(d => (
              <div key={d.live_id}
                className={`p-3 rounded-lg border flex items-center justify-between ${
                  d.status === 'active' ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-gray-50'
                }`}>
                <div>
                  <span className="font-medium text-gray-800">{d.strategy_id}</span>
                  <span className={`ml-2 text-xs px-1.5 py-0.5 rounded-full ${
                    d.status === 'active' ? 'bg-green-200 text-green-800' : 'bg-gray-200 text-gray-600'
                  }`}>{d.status === 'active' ? '● 运行中' : '■ 已停止'}</span>
                  <div className="text-xs text-gray-500 mt-0.5 space-x-3">
                    <span>初始资金：¥{d.initial_cash?.toLocaleString()}</span>
                    <span>风控：{d.risk_mode}</span>
                    <span>部署：{d.deployed_at?.slice(0, 10)}</span>
                    {d.metrics?.sharpe != null && <span>Sharpe：{Number(d.metrics.sharpe).toFixed(3)}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2 ml-4 flex-shrink-0">
                  <button
                    onClick={() => setSelectedLiveId(selectedLiveId === d.live_id ? null : d.live_id)}
                    className="btn-secondary text-xs"
                  >
                    {selectedLiveId === d.live_id ? '隐藏记录' : '执行记录'}
                  </button>
                  {d.status === 'active' && (
                    <button
                      disabled={stopMutation.isPending}
                      onClick={() => {
                        if (!confirm(`确认停止模拟策略 ${d.strategy_id}？`)) return
                        stopMutation.mutate(d.live_id)
                      }}
                      className="btn-secondary text-xs disabled:opacity-50"
                    >
                      {stopMutation.isPending ? '停止中…' : '停止'}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Execution History */}
      {selectedLiveId && executions && (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-800">
              执行记录
              <span className="text-xs text-gray-500 ml-2">共 {executions.total} 条</span>
            </h2>
            <span className="text-xs text-gray-400 font-mono">{selectedLiveId}</span>
          </div>

          {/* Execution summary cards */}
          {executions.items.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
              <div className="text-center p-2 bg-gray-50 rounded-lg">
                <div className="text-lg font-bold text-brand-600">{executions.items.length}</div>
                <div className="text-xs text-gray-500">总订单</div>
              </div>
              <div className="text-center p-2 bg-green-50 rounded-lg">
                <div className="text-lg font-bold text-green-600">
                  {executions.items.filter(e => e.status === 'filled').length}
                </div>
                <div className="text-xs text-gray-500">已成交</div>
              </div>
              <div className="text-center p-2 bg-red-50 rounded-lg">
                <div className="text-lg font-bold text-red-600">
                  {executions.items.filter(e => e.status === 'rejected').length}
                </div>
                <div className="text-xs text-gray-500">已拒绝</div>
              </div>
              <div className="text-center p-2 bg-gray-50 rounded-lg">
                <div className="text-lg font-bold text-gray-600">
                  {executions.items.reduce((sum, e) => sum + e.total_cost, 0).toFixed(2)}
                </div>
                <div className="text-xs text-gray-500">总费用</div>
              </div>
            </div>
          )}

          {/* Execution log table */}
          {executions.items.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="table-th">时间</th>
                    <th className="table-th">资产</th>
                    <th className="table-th">方向</th>
                    <th className="table-th text-right">数量</th>
                    <th className="table-th text-right">成交价</th>
                    <th className="table-th text-right">费用</th>
                    <th className="table-th">状态</th>
                  </tr>
                </thead>
                <tbody>
                  {executions.items.map((ex: LiveExecution) => (
                    <tr key={ex.execution_id} className="table-row">
                      <td className="table-td text-gray-400">{ex.executed_at?.slice(0, 16) ?? '—'}</td>
                      <td className="table-td font-mono">{ex.asset_id}</td>
                      <td className="table-td">
                        <span className={`badge ${ex.side === 'buy' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}`}>
                          {ex.side === 'buy' ? '买入' : '卖出'}
                        </span>
                      </td>
                      <td className="table-td text-right">{ex.filled_qty.toLocaleString()}</td>
                      <td className="table-td text-right">{ex.filled_price.toFixed(2)}</td>
                      <td className="table-td text-right text-gray-500">{ex.total_cost.toFixed(2)}</td>
                      <td className="table-td">
                        <span className={`badge ${
                          ex.status === 'filled' ? 'bg-green-100 text-green-800' :
                          ex.status === 'rejected' ? 'bg-red-100 text-red-800' :
                          'bg-gray-100 text-gray-600'
                        }`}>
                          {ex.status === 'filled' ? '已成交' : ex.status === 'rejected' ? '已拒绝' : ex.status}
                        </span>
                        {ex.reject_reason && (
                          <span className="ml-1 text-red-500" title={ex.reject_reason}>(?)</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center text-gray-400 py-8">
              <div className="text-3xl mb-2">📋</div>
              <div>暂无执行记录</div>
              <p className="text-xs mt-1">策略执行后会在此显示订单记录</p>
            </div>
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
              {pnlData ? `${pnlData.total_pnl >= 0 ? '+' : ''}${pnlData.total_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—'}
            </div>
            <div className="text-xs text-gray-500 mt-1">总盈亏</div>
          </div>
          <div className="card text-center">
            <div className={`text-xl font-bold ${(pnlData?.return_pct ?? 0) >= 0 ? 'text-red-600' : 'text-green-600'}`}>
              {pnlData ? `${pnlData.return_pct >= 0 ? '+' : ''}${pnlData.return_pct.toFixed(2)}%` : '—'}
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

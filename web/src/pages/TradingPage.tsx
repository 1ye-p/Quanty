import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { tradingApi, realtimeApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { OrderForm } from '@/components/trading/OrderForm'
import { PositionTable } from '@/components/trading/PositionTable'
import { OrderBook } from '@/components/trading/OrderBook'
import { AccountInfo } from '@/components/trading/AccountInfo'
import { OrderHistory } from '@/components/trading/OrderHistory'
import { TradeHistory } from '@/components/trading/TradeHistory'

const tabs = [
  { id: 'order', label: '下单' },
  { id: 'account', label: '账户' },
  { id: 'orders', label: '订单历史' },
  { id: 'trades', label: '成交回报' },
] as const

type TradingTab = typeof tabs[number]['id']

export function TradingPage() {
  const [broker, setBroker] = useState('paper')
  const [activeTab, setActiveTab] = useState<TradingTab>('order')
  const [lookupSymbol, setLookupSymbol] = useState('')
  const [showLookup, setShowLookup] = useState(false)
  const queryClient = useQueryClient()

  // Account data
  const { data: account } = useQuery({
    queryKey: extendedQueryKeys.trading.account(broker),
    queryFn: () => tradingApi.account(broker),
    refetchInterval: 5000,
  })

  // Quote lookup
  const { data: quoteData, isLoading: quoteLoading } = useQuery({
    queryKey: extendedQueryKeys.realtime.quote(lookupSymbol),
    queryFn: () => realtimeApi.quote(lookupSymbol),
    enabled: showLookup && lookupSymbol.length >= 6,
  })

  const handleOrderPlaced = () => {
    queryClient.invalidateQueries({ queryKey: extendedQueryKeys.trading.orders(broker) })
    queryClient.invalidateQueries({ queryKey: extendedQueryKeys.trading.positions(broker) })
    queryClient.invalidateQueries({ queryKey: extendedQueryKeys.trading.account(broker) })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title">交易中心</h1>
          <p className="page-subtitle">下单 · 持仓 · 订单管理</p>
        </div>

        {/* Broker Selector */}
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">券商:</span>
          <select
            className="input"
            value={broker}
            onChange={e => setBroker(e.target.value)}
          >
            <option value="paper">Paper Trading</option>
            <option value="qmt">QMT (迅投)</option>
          </select>
        </div>
      </div>

      {/* Tab Bar */}
      <div className="flex gap-1 border-b mb-6">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab: 下单 (Order) */}
      {activeTab === 'order' && (
        <>
          {/* Quote Lookup */}
          <div className="card">
            <div className="flex items-center gap-3 mb-4">
              <h2 className="font-semibold text-gray-800">行情查询</h2>
              <input
                type="text"
                value={lookupSymbol}
                onChange={e => {
                  setLookupSymbol(e.target.value)
                  setShowLookup(true)
                }}
                placeholder="输入股票代码 (600036)"
                className="input flex-1"
              />
            </div>

            {showLookup && lookupSymbol.length >= 6 && (
              <>
                {quoteLoading && <p className="text-gray-400 text-sm">查询中...</p>}
                {quoteData && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <div>
                      <div className="text-sm text-gray-500">最新价</div>
                      <div className="text-xl font-bold">{quoteData.price.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-500">涨跌幅</div>
                      <div className={`text-xl font-bold ${quoteData.change_pct >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {quoteData.change_pct >= 0 ? '+' : ''}{quoteData.change_pct.toFixed(2)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-500">成交量</div>
                      <div className="text-xl font-bold">{(quoteData.volume / 10000).toFixed(0)}万</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-500">成交额</div>
                      <div className="text-xl font-bold">{(quoteData.amount / 100000000).toFixed(2)}亿</div>
                    </div>
                    <div className="col-span-2 sm:col-span-4">
                      <div className="flex gap-4 text-sm">
                        <span>开盘: {quoteData.open.toFixed(2)}</span>
                        <span className="text-red-600">最高: {quoteData.high.toFixed(2)}</span>
                        <span className="text-green-600">最低: {quoteData.low.toFixed(2)}</span>
                        <span>昨收: {quoteData.prev_close.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Main Content */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left: Positions + Orders */}
            <div className="lg:col-span-2 space-y-6">
              <PositionTable broker={broker} />
              <OrderBook broker={broker} />
            </div>

            {/* Right: Order Form */}
            <div>
              <OrderForm broker={broker} onOrderPlaced={handleOrderPlaced} />
            </div>
          </div>
        </>
      )}

      {/* Tab: 账户 (Account) */}
      {activeTab === 'account' && <AccountInfo broker={broker} />}

      {/* Tab: 订单历史 (Order History) */}
      {activeTab === 'orders' && <OrderHistory broker={broker} />}

      {/* Tab: 成交回报 (Trade History) */}
      {activeTab === 'trades' && <TradeHistory broker={broker} />}
    </div>
  )
}

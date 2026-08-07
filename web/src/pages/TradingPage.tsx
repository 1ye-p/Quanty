import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { tradingApi, realtimeApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { OrderForm } from '@/components/trading/OrderForm'
import { PositionTable } from '@/components/trading/PositionTable'
import { OrderBook } from '@/components/trading/OrderBook'
import { AccountInfo } from '@/components/trading/AccountInfo'
import { OrderHistory } from '@/components/trading/OrderHistory'
import { TradeHistory } from '@/components/trading/TradeHistory'
import { AlgoOrderForm } from '@/components/trading/AlgoOrderForm'
import { AlgoOrderMonitor } from '@/components/trading/AlgoOrderMonitor'

const tabs = [
  { id: 'order' },
  { id: 'algo' },
  { id: 'account' },
  { id: 'orders' },
  { id: 'trades' },
] as const

type TradingTab = typeof tabs[number]['id']

export function TradingPage() {
  const { t } = useTranslation()
  const [broker, setBroker] = useState('paper')
  const [activeTab, setActiveTab] = useState<TradingTab>('order')
  const [lookupSymbol, setLookupSymbol] = useState('')
  const [showLookup, setShowLookup] = useState(false)
  const queryClient = useQueryClient()

  // Account data (pre-fetch for cache; AccountInfo fetches its own view)
  useQuery({
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

  // Algo orders list
  const { data: algoOrdersData } = useQuery({
    queryKey: extendedQueryKeys.trading.algoOrders(),
    queryFn: () => tradingApi.listAlgoOrders(),
    refetchInterval: 5000,
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
          <h1 className="page-title">{t('page.trading.title')}</h1>
          <p className="page-subtitle">{t('page.trading.subtitle')}</p>
        </div>

        {/* Broker Selector */}
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">{t('page.trading.broker.label')}</span>
          <select
            className="input"
            value={broker}
            onChange={e => setBroker(e.target.value)}
          >
            <option value="paper">{t('page.trading.broker.paper')}</option>
            <option value="qmt">{t('page.trading.broker.qmt')}</option>
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
            {t(`page.trading.tab.${tab.id}`)}
          </button>
        ))}
      </div>

      {/* Tab: 下单 (Order) */}
      {activeTab === 'order' && (
        <>
          {/* Quote Lookup */}
          <div className="card">
            <div className="flex items-center gap-3 mb-4">
              <h2 className="font-semibold text-gray-800">{t('page.trading.quote.section_title')}</h2>
              <input
                type="text"
                value={lookupSymbol}
                onChange={e => {
                  setLookupSymbol(e.target.value)
                  setShowLookup(true)
                }}
                placeholder={t('page.trading.quote.placeholder')}
                className="input flex-1"
              />
            </div>

            {showLookup && lookupSymbol.length >= 6 && (
              <>
                {quoteLoading && <p className="text-gray-400 text-sm">{t('page.trading.quote.querying')}</p>}
                {quoteData && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <div>
                      <div className="text-sm text-gray-500">{t('page.trading.quote.last_price')}</div>
                      <div className="text-xl font-bold">{quoteData.price.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-500">{t('page.trading.quote.change_pct')}</div>
                      <div className={`text-xl font-bold ${quoteData.change_pct >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {quoteData.change_pct >= 0 ? '+' : ''}{quoteData.change_pct.toFixed(2)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-500">{t('page.trading.quote.volume')}</div>
                      <div className="text-xl font-bold">{(quoteData.volume / 10000).toFixed(0)}{t('page.trading.quote.volume_unit_wan')}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-500">{t('page.trading.quote.amount')}</div>
                      <div className="text-xl font-bold">{(quoteData.amount / 100000000).toFixed(2)}{t('page.trading.quote.amount_unit_yi')}</div>
                    </div>
                    <div className="col-span-2 sm:col-span-4">
                      <div className="flex gap-4 text-sm">
                        <span>{t('page.trading.quote.open')}: {quoteData.open.toFixed(2)}</span>
                        <span className="text-red-600">{t('page.trading.quote.high')}: {quoteData.high.toFixed(2)}</span>
                        <span className="text-green-600">{t('page.trading.quote.low')}: {quoteData.low.toFixed(2)}</span>
                        <span>{t('page.trading.quote.prev_close')}: {quoteData.prev_close.toFixed(2)}</span>
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

      {/* Tab: 算法下单 (Algo Orders) */}
      {activeTab === 'algo' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Active algo orders + monitors */}
          <div className="lg:col-span-2 space-y-4">
            <h2 className="font-semibold text-gray-800">{t('page.trading.algo.active_title')}</h2>
            {algoOrdersData?.items && algoOrdersData.items.length > 0 ? (
              algoOrdersData.items
                .filter(o => o.status === 'active')
                .map(o => (
                  <AlgoOrderMonitor key={o.order_id} orderId={o.order_id} broker={broker} />
                ))
            ) : (
              <div className="bg-white rounded-xl shadow-sm border p-4">
                <p className="text-gray-400 text-sm">{t('page.trading.algo.active_empty')}</p>
              </div>
            )}

            {/* Completed orders summary */}
            {algoOrdersData?.items && algoOrdersData.items.filter(o => o.status !== 'active').length > 0 && (
              <div className="bg-white rounded-xl shadow-sm border p-4">
                <h3 className="font-semibold text-gray-700 mb-3">{t('page.trading.algo.completed_title')}</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 border-b">
                        <th className="pb-2 pr-3">{t('page.trading.algo.column_order_id')}</th>
                        <th className="pb-2 pr-3">{t('page.trading.algo.column_type')}</th>
                        <th className="pb-2 pr-3">{t('page.trading.algo.column_symbol')}</th>
                        <th className="pb-2 pr-3">{t('page.trading.algo.column_side')}</th>
                        <th className="pb-2 pr-3">{t('page.trading.algo.column_filled')}</th>
                        <th className="pb-2 pr-3">{t('page.trading.algo.column_avg_price')}</th>
                        <th className="pb-2">{t('page.trading.algo.column_status')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {algoOrdersData.items
                        .filter(o => o.status !== 'active')
                        .map(o => (
                          <tr key={o.order_id} className="border-b last:border-0">
                            <td className="py-2 pr-3 font-mono text-xs">{o.order_id.slice(0, 8)}</td>
                            <td className="py-2 pr-3">{o.order_type.toUpperCase()}</td>
                            <td className="py-2 pr-3">{o.asset_id}</td>
                            <td className="py-2 pr-3">{o.side === 'buy' ? t('page.trading.algo.side_buy') : t('page.trading.algo.side_sell')}</td>
                            <td className="py-2 pr-3">{o.filled_qty}</td>
                            <td className="py-2 pr-3">{o.avg_price > 0 ? o.avg_price.toFixed(2) : t('page.trading.algo.status_dash')}</td>
                            <td className="py-2">
                              <span className={o.status === 'completed' ? 'text-green-600' : 'text-red-500'}>
                                {o.status === 'completed' ? t('page.trading.algo.status_completed') : o.status === 'cancelled' ? t('page.trading.algo.status_cancelled') : t('page.trading.algo.status_failed')}
                              </span>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Right: Algo Order Form */}
          <div>
            <AlgoOrderForm broker={broker} onSubmitted={() => {
              queryClient.invalidateQueries({ queryKey: extendedQueryKeys.trading.algoOrders() })
            }} />
          </div>
        </div>
      )}

      {/* Tab: 订单历史 (Order History) */}
      {activeTab === 'orders' && <OrderHistory broker={broker} />}

      {/* Tab: 成交回报 (Trade History) */}
      {activeTab === 'trades' && <TradeHistory broker={broker} />}
    </div>
  )
}

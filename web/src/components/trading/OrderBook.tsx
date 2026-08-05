import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { tradingApi, type TradeOrder } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'

interface OrderBookProps {
  broker?: string
}

export function OrderBook({ broker = 'paper' }: OrderBookProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: extendedQueryKeys.trading.orders(broker),
    queryFn: () => tradingApi.orders(broker),
    refetchInterval: 5000,
  })

  const cancelMutation = useMutation({
    mutationFn: (orderId: string) => tradingApi.cancelOrder(orderId, broker),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: extendedQueryKeys.trading.orders(broker) })
    },
  })

  if (isLoading) {
    return <div className="card text-gray-400">{t('component.trading.order_book.loading')}</div>
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="card">
        <h2 className="font-semibold text-gray-800 mb-2">{t('component.trading.order_book.title')}</h2>
        <p className="text-gray-400 text-sm">{t('component.trading.order_book.empty')}</p>
      </div>
    )
  }

  const statusColor = (status: string) => {
    switch (status) {
      case 'filled': return 'text-green-600 bg-green-50'
      case 'rejected': return 'text-red-600 bg-red-50'
      case 'cancelled': return 'text-gray-500 bg-gray-50'
      case 'submitted': return 'text-blue-600 bg-blue-50'
      default: return 'text-yellow-600 bg-yellow-50'
    }
  }

  const statusLabelKey = (status: string): string => {
    switch (status) {
      case 'filled': return 'component.trading.order_book.status.filled'
      case 'rejected': return 'component.trading.order_book.status.rejected'
      case 'cancelled': return 'component.trading.order_book.status.cancelled'
      case 'submitted': return 'component.trading.order_book.status.submitted'
      case 'pending': return 'component.trading.order_book.status.pending'
      case 'partial_filled': return 'component.trading.order_book.status.partial_filled'
      default: return ''
    }
  }

  return (
    <div className="card">
      <h2 className="font-semibold text-gray-800 mb-4">
        {t('component.trading.order_book.title')} <span className="text-sm font-normal text-gray-400">({data.total})</span>
      </h2>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="pb-2 pr-3">{t('component.trading.order_book.col_id')}</th>
              <th className="pb-2 pr-3">{t('component.trading.shared.col_asset')}</th>
              <th className="pb-2 pr-3">{t('component.trading.shared.col_side')}</th>
              <th className="pb-2 pr-3 text-right">{t('component.trading.shared.col_qty')}</th>
              <th className="pb-2 pr-3 text-right">{t('component.trading.shared.col_filled_price')}</th>
              <th className="pb-2 pr-3">{t('component.trading.shared.col_status')}</th>
              <th className="pb-2">{t('component.trading.order_book.col_action')}</th>
            </tr>
          </thead>
          <tbody>
            {data.items.slice(0, 20).map((order: TradeOrder) => {
              const labelKey = statusLabelKey(order.status)
              return (
                <tr key={order.order_id} className="border-b last:border-0">
                  <td className="py-2 pr-3 font-mono text-xs">{order.order_id}</td>
                  <td className="py-2 pr-3 font-mono">{order.asset_id.split(':')[1]}</td>
                  <td className="py-2 pr-3">
                    <span className={order.side === 'buy' ? 'text-red-600' : 'text-green-600'}>
                      {order.side === 'buy' ? t('component.trading.shared.side_buy') : t('component.trading.shared.side_sell')}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-right">{order.qty.toLocaleString()}</td>
                  <td className="py-2 pr-3 text-right">
                    {order.filled_price > 0 ? order.filled_price.toFixed(2) : t('component.trading.shared.dash')}
                  </td>
                  <td className="py-2 pr-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${statusColor(order.status)}`}>
                      {labelKey ? t(labelKey) : order.status}
                    </span>
                  </td>
                  <td className="py-2">
                    {(order.status === 'pending' || order.status === 'submitted') && (
                      <button
                        onClick={() => cancelMutation.mutate(order.order_id)}
                        disabled={cancelMutation.isPending}
                        className="text-red-500 hover:text-red-700 text-xs"
                      >
                        {t('component.trading.order_book.cancel')}
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

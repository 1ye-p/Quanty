import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { tradingApi } from '@/lib/api/trading'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { cn } from '@/lib/utils'

interface Props {
  broker?: string
}

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  filled: 'bg-green-100 text-green-700',
  partial: 'bg-blue-100 text-blue-700',
  cancelled: 'bg-gray-100 text-gray-700',
  rejected: 'bg-red-100 text-red-700',
}

const statusKeys: Record<string, string> = {
  pending: 'component.trading.order_history.status.pending',
  filled: 'component.trading.order_history.status.filled',
  partial: 'component.trading.order_history.status.partial',
  cancelled: 'component.trading.order_history.status.cancelled',
  rejected: 'component.trading.order_history.status.rejected',
}

export function OrderHistory({ broker = 'paper' }: Props) {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: extendedQueryKeys.trading.orders(broker),
    queryFn: () => tradingApi.orders(broker),
    refetchInterval: 10000,
  })

  if (isLoading) return <div className="card text-center py-4 text-gray-500">{t('common.loading')}</div>
  if (error) return <div className="card text-center py-4 text-red-500">{t('component.trading.shared.loading_failed')}</div>
  const orders = data?.items ?? []
  if (!orders.length) return <div className="card text-center py-8 text-gray-400">{t('component.trading.order_book.empty')}</div>

  return (
    <div className="card">
      <h3 className="font-medium text-gray-800 mb-4">{t('component.trading.order_history.title')}</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="pb-2 pr-4">{t('component.trading.shared.col_time')}</th>
              <th className="pb-2 pr-4">{t('component.trading.shared.col_symbol')}</th>
              <th className="pb-2 pr-4">{t('component.trading.shared.col_side')}</th>
              <th className="pb-2 pr-4 text-right">{t('component.trading.order_history.col_order_qty')}</th>
              <th className="pb-2 pr-4 text-right">{t('component.trading.shared.col_filled_qty')}</th>
              <th className="pb-2 pr-4 text-right">{t('component.trading.shared.col_filled_price')}</th>
              <th className="pb-2">{t('component.trading.shared.col_status')}</th>
            </tr>
          </thead>
          <tbody>
            {orders.map(order => (
              <tr key={order.order_id} className="border-b last:border-0">
                <td className="py-2 pr-4 text-gray-500">
                  {order.submitted_at ? new Date(order.submitted_at).toLocaleString('zh-CN') : '-'}
                </td>
                <td className="py-2 pr-4 font-mono">{order.asset_id}</td>
                <td className={cn('py-2 pr-4', order.side === 'buy' ? 'text-red-600' : 'text-green-600')}>
                  {order.side === 'buy' ? t('component.trading.shared.side_buy') : t('component.trading.shared.side_sell')}
                </td>
                <td className="py-2 pr-4 text-right">{order.qty.toLocaleString()}</td>
                <td className="py-2 pr-4 text-right">{order.filled_qty ? order.filled_qty.toLocaleString() : '-'}</td>
                <td className="py-2 pr-4 text-right">{order.filled_price?.toFixed(2) || '-'}</td>
                <td className="py-2">
                  <span className={cn('text-xs px-2 py-0.5 rounded', statusColors[order.status] ?? 'bg-gray-100 text-gray-700')}>
                    {statusKeys[order.status] ? t(statusKeys[order.status]) : order.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

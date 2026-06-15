import { useQuery } from '@tanstack/react-query'
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

const statusLabels: Record<string, string> = {
  pending: '待成交',
  filled: '已成交',
  partial: '部分成交',
  cancelled: '已撤单',
  rejected: '已拒绝',
}

export function OrderHistory({ broker = 'paper' }: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: extendedQueryKeys.trading.orders(broker),
    queryFn: () => tradingApi.orders(broker),
    refetchInterval: 10000,
  })

  if (isLoading) return <div className="card text-center py-4 text-gray-500">加载中...</div>
  if (error) return <div className="card text-center py-4 text-red-500">加载失败</div>
  const orders = data?.items ?? []
  if (!orders.length) return <div className="card text-center py-8 text-gray-400">暂无订单</div>

  return (
    <div className="card">
      <h3 className="font-medium text-gray-800 mb-4">订单历史</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="pb-2 pr-4">时间</th>
              <th className="pb-2 pr-4">标的</th>
              <th className="pb-2 pr-4">方向</th>
              <th className="pb-2 pr-4 text-right">委托量</th>
              <th className="pb-2 pr-4 text-right">成交量</th>
              <th className="pb-2 pr-4 text-right">成交价</th>
              <th className="pb-2">状态</th>
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
                  {order.side === 'buy' ? '买入' : '卖出'}
                </td>
                <td className="py-2 pr-4 text-right">{order.qty.toLocaleString()}</td>
                <td className="py-2 pr-4 text-right">{order.filled_qty ? order.filled_qty.toLocaleString() : '-'}</td>
                <td className="py-2 pr-4 text-right">{order.filled_price?.toFixed(2) || '-'}</td>
                <td className="py-2">
                  <span className={cn('text-xs px-2 py-0.5 rounded', statusColors[order.status] ?? 'bg-gray-100 text-gray-700')}>
                    {statusLabels[order.status] ?? order.status}
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

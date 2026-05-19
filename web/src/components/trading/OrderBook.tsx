import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tradingApi, type TradeOrder } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'

interface OrderBookProps {
  broker?: string
}

export function OrderBook({ broker = 'paper' }: OrderBookProps) {
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
    return <div className="card text-gray-400">Loading orders...</div>
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="card">
        <h2 className="font-semibold text-gray-800 mb-2">订单</h2>
        <p className="text-gray-400 text-sm">暂无订单</p>
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

  const statusLabel = (status: string) => {
    switch (status) {
      case 'filled': return '已成交'
      case 'rejected': return '已拒绝'
      case 'cancelled': return '已撤销'
      case 'submitted': return '已提交'
      case 'pending': return '待处理'
      case 'partial_filled': return '部分成交'
      default: return status
    }
  }

  return (
    <div className="card">
      <h2 className="font-semibold text-gray-800 mb-4">
        订单 <span className="text-sm font-normal text-gray-400">({data.total})</span>
      </h2>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="pb-2 pr-3">ID</th>
              <th className="pb-2 pr-3">资产</th>
              <th className="pb-2 pr-3">方向</th>
              <th className="pb-2 pr-3 text-right">数量</th>
              <th className="pb-2 pr-3 text-right">成交价</th>
              <th className="pb-2 pr-3">状态</th>
              <th className="pb-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {data.items.slice(0, 20).map((order: TradeOrder) => (
              <tr key={order.order_id} className="border-b last:border-0">
                <td className="py-2 pr-3 font-mono text-xs">{order.order_id}</td>
                <td className="py-2 pr-3 font-mono">{order.asset_id.split(':')[1]}</td>
                <td className="py-2 pr-3">
                  <span className={order.side === 'buy' ? 'text-red-600' : 'text-green-600'}>
                    {order.side === 'buy' ? '买' : '卖'}
                  </span>
                </td>
                <td className="py-2 pr-3 text-right">{order.qty.toLocaleString()}</td>
                <td className="py-2 pr-3 text-right">
                  {order.filled_price > 0 ? order.filled_price.toFixed(2) : '—'}
                </td>
                <td className="py-2 pr-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs ${statusColor(order.status)}`}>
                    {statusLabel(order.status)}
                  </span>
                </td>
                <td className="py-2">
                  {(order.status === 'pending' || order.status === 'submitted') && (
                    <button
                      onClick={() => cancelMutation.mutate(order.order_id)}
                      disabled={cancelMutation.isPending}
                      className="text-red-500 hover:text-red-700 text-xs"
                    >
                      撤单
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

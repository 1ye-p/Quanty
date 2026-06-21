import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tradingApi } from '@/lib/api/trading'
import { extendedQueryKeys } from '@/lib/queryKeys'

interface AlgoOrderMonitorProps {
  orderId: string
  broker?: string
}

const STATUS_LABEL: Record<string, { text: string; color: string }> = {
  pending: { text: '待执行', 'color': 'text-gray-500' },
  filled: { text: '已成交', color: 'text-green-600' },
  cancelled: { text: '已取消', color: 'text-yellow-600' },
  failed: { text: '失败', color: 'text-red-600' },
}

const ORDER_STATUS_LABEL: Record<string, { text: string; color: string }> = {
  active: { text: '执行中', color: 'text-blue-600' },
  completed: { text: '已完成', color: 'text-green-600' },
  cancelled: { text: '已取消', color: 'text-yellow-600' },
  failed: { text: '失败', color: 'text-red-600' },
}

export function AlgoOrderMonitor({ orderId, broker = 'paper' }: AlgoOrderMonitorProps) {
  const queryClient = useQueryClient()

  const { data: order, isLoading, error } = useQuery({
    queryKey: ['trading', 'algo-order', orderId],
    queryFn: () => tradingApi.getAlgoOrder(orderId),
    refetchInterval: (query) => {
      // Poll every 3s while active
      const status = query.state.data?.status
      return status === 'active' ? 3000 : false
    },
  })

  const cancelMutation = useMutation({
    mutationFn: () => tradingApi.cancelAlgoOrder(orderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trading', 'algo-order', orderId] })
      queryClient.invalidateQueries({ queryKey: extendedQueryKeys.trading.orders(broker) })
    },
  })

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <p className="text-gray-400 text-sm">加载中...</p>
      </div>
    )
  }

  if (error || !order) {
    return (
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <p className="text-red-500 text-sm">无法加载订单状态</p>
      </div>
    )
  }

  const totalSlices = order.slices.length
  const completedSlices = order.slices.filter(s => s.status === 'filled').length
  const progressPct = totalSlices > 0 ? (completedSlices / totalSlices) * 100 : 0

  const statusInfo = ORDER_STATUS_LABEL[order.status] ?? { text: order.status, color: 'text-gray-500' }

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-800">
            算法订单 {order.order_id.slice(0, 8)}...
          </h3>
          <p className="text-sm text-gray-500">
            {order.order_type.toUpperCase()} | {order.asset_id} |{' '}
            {order.side === 'buy' ? '买入' : '卖出'} {order.total_qty} 股
          </p>
        </div>
        <span className={`text-sm font-medium ${statusInfo.color}`}>
          {statusInfo.text}
        </span>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>执行进度</span>
          <span>{completedSlices} / {totalSlices} 片</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2.5">
          <div
            className="bg-blue-500 h-2.5 rounded-full transition-all"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* Cumulative stats */}
      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="bg-gray-50 rounded-lg p-2">
          <div className="text-xs text-gray-500">已成交数量</div>
          <div className="text-sm font-semibold">{order.filled_qty}</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-2">
          <div className="text-xs text-gray-500">成交均价</div>
          <div className="text-sm font-semibold">
            {order.avg_price > 0 ? order.avg_price.toFixed(2) : '—'}
          </div>
        </div>
        <div className="bg-gray-50 rounded-lg p-2">
          <div className="text-xs text-gray-500">滑点</div>
          <div className={`text-sm font-semibold ${order.slippage > 0 ? 'text-red-600' : 'text-green-600'}`}>
            {order.slippage !== 0 ? `${order.slippage.toFixed(4)}%` : '—'}
          </div>
        </div>
      </div>

      {/* Slice details table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="pb-2 pr-3">分片 ID</th>
              <th className="pb-2 pr-3">计划时间</th>
              <th className="pb-2 pr-3">状态</th>
              <th className="pb-2 pr-3">成交价</th>
              <th className="pb-2">成交量</th>
            </tr>
          </thead>
          <tbody>
            {order.slices.map(slice => {
              const sliceStatus = STATUS_LABEL[slice.status] ?? { text: slice.status, color: 'text-gray-500' }
              return (
                <tr key={slice.slice_id} className="border-b last:border-0">
                  <td className="py-2 pr-3 font-mono text-xs">{slice.slice_id.slice(0, 8)}</td>
                  <td className="py-2 pr-3 text-gray-600">
                    {new Date(slice.scheduled_time).toLocaleString('zh-CN', {
                      month: '2-digit',
                      day: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </td>
                  <td className={`py-2 pr-3 ${sliceStatus.color}`}>{sliceStatus.text}</td>
                  <td className="py-2 pr-3">{slice.filled_price?.toFixed(2) ?? '—'}</td>
                  <td className="py-2">{slice.filled_qty ?? '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Cancel button */}
      {order.status === 'active' && (
        <button
          onClick={() => cancelMutation.mutate()}
          disabled={cancelMutation.isPending}
          className="w-full py-2 rounded-lg bg-red-50 hover:bg-red-100 text-red-600 text-sm font-medium transition-colors disabled:opacity-50"
        >
          {cancelMutation.isPending ? '取消中...' : '取消算法订单'}
        </button>
      )}

      {cancelMutation.isError && (
        <p className="text-red-500 text-sm">{cancelMutation.error?.message || '取消失败'}</p>
      )}
    </div>
  )
}

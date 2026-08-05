import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { tradingApi } from '@/lib/api/trading'
import { extendedQueryKeys } from '@/lib/queryKeys'

interface AlgoOrderMonitorProps {
  orderId: string
  broker?: string
}

const SLICE_STATUS_COLOR: Record<string, string> = {
  pending: 'text-gray-500',
  filled: 'text-green-600',
  cancelled: 'text-yellow-600',
  failed: 'text-red-600',
}

const ORDER_STATUS_COLOR: Record<string, string> = {
  active: 'text-blue-600',
  completed: 'text-green-600',
  cancelled: 'text-yellow-600',
  failed: 'text-red-600',
}

export function AlgoOrderMonitor({ orderId, broker = 'paper' }: AlgoOrderMonitorProps) {
  const { t } = useTranslation()
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
        <p className="text-gray-400 text-sm">{t('component.trading.algo_order_monitor.loading')}</p>
      </div>
    )
  }

  if (error || !order) {
    return (
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <p className="text-red-500 text-sm">{t('component.trading.algo_order_monitor.load_failed')}</p>
      </div>
    )
  }

  const totalSlices = order.slices.length
  const completedSlices = order.slices.filter(s => s.status === 'filled').length
  const progressPct = totalSlices > 0 ? (completedSlices / totalSlices) * 100 : 0

  const statusColor = ORDER_STATUS_COLOR[order.status] ?? 'text-gray-500'
  const statusKey = `component.trading.algo_order_monitor.order_status.${order.status}`
  const statusText = ORDER_STATUS_COLOR[order.status] ? t(statusKey) : order.status

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-800">
            {t('component.trading.algo_order_monitor.title', { id: order.order_id.slice(0, 8) })}...
          </h3>
          <p className="text-sm text-gray-500">
            {t('component.trading.algo_order_monitor.summary', {
              type: order.order_type.toUpperCase(),
              symbol: order.asset_id,
              side: order.side === 'buy' ? t('component.trading.shared.side_buy') : t('component.trading.shared.side_sell'),
              qty: order.total_qty,
            })}
          </p>
        </div>
        <span className={`text-sm font-medium ${statusColor}`}>
          {statusText}
        </span>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>{t('component.trading.algo_order_monitor.progress')}</span>
          <span>{t('component.trading.algo_order_monitor.slices_unit', { completed: completedSlices, total: totalSlices })}</span>
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
          <div className="text-xs text-gray-500">{t('component.trading.algo_order_monitor.filled_qty')}</div>
          <div className="text-sm font-semibold">{order.filled_qty}</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-2">
          <div className="text-xs text-gray-500">{t('component.trading.algo_order_monitor.avg_price')}</div>
          <div className="text-sm font-semibold">
            {order.avg_price > 0 ? order.avg_price.toFixed(2) : t('component.trading.shared.dash')}
          </div>
        </div>
        <div className="bg-gray-50 rounded-lg p-2">
          <div className="text-xs text-gray-500">{t('component.trading.algo_order_monitor.slippage')}</div>
          <div className={`text-sm font-semibold ${order.slippage > 0 ? 'text-red-600' : 'text-green-600'}`}>
            {order.slippage !== 0 ? `${order.slippage.toFixed(4)}%` : t('component.trading.shared.dash')}
          </div>
        </div>
      </div>

      {/* Slice details table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="pb-2 pr-3">{t('component.trading.algo_order_monitor.col_slice_id')}</th>
              <th className="pb-2 pr-3">{t('component.trading.algo_order_monitor.col_scheduled_time')}</th>
              <th className="pb-2 pr-3">{t('component.trading.shared.col_status')}</th>
              <th className="pb-2 pr-3">{t('component.trading.algo_order_monitor.col_filled_price')}</th>
              <th className="pb-2">{t('component.trading.algo_order_monitor.col_filled_qty')}</th>
            </tr>
          </thead>
          <tbody>
            {order.slices.map(slice => {
              const sliceColor = SLICE_STATUS_COLOR[slice.status] ?? 'text-gray-500'
              const sliceKey = `component.trading.algo_order_monitor.slice_status.${slice.status}`
              const sliceText = SLICE_STATUS_COLOR[slice.status] ? t(sliceKey) : slice.status
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
                  <td className={`py-2 pr-3 ${sliceColor}`}>{sliceText}</td>
                  <td className="py-2 pr-3">{slice.filled_price?.toFixed(2) ?? t('component.trading.shared.dash')}</td>
                  <td className="py-2">{slice.filled_qty ?? t('component.trading.shared.dash')}</td>
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
          {cancelMutation.isPending ? t('component.trading.algo_order_monitor.cancelling') : t('component.trading.algo_order_monitor.cancel')}
        </button>
      )}

      {cancelMutation.isError && (
        <p className="text-red-500 text-sm">{cancelMutation.error?.message || t('component.trading.algo_order_monitor.cancel_failed')}</p>
      )}
    </div>
  )
}

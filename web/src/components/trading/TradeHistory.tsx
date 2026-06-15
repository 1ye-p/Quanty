import { useQuery } from '@tanstack/react-query'
import { tradingApi } from '@/lib/api/trading'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { cn } from '@/lib/utils'

interface Props {
  broker?: string
}

export function TradeHistory({ broker = 'paper' }: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: extendedQueryKeys.trading.fills(broker),
    queryFn: () => tradingApi.fills(broker),
    refetchInterval: 10000,
  })

  if (isLoading) return <div className="card text-center py-4 text-gray-500">加载中...</div>
  if (error) return <div className="card text-center py-4 text-red-500">加载失败</div>
  const trades = data?.items ?? []
  if (!trades.length) return <div className="card text-center py-8 text-gray-400">暂无成交记录</div>

  return (
    <div className="card">
      <h3 className="font-medium text-gray-800 mb-4">成交回报</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="pb-2 pr-4">时间</th>
              <th className="pb-2 pr-4">标的</th>
              <th className="pb-2 pr-4">方向</th>
              <th className="pb-2 pr-4 text-right">成交量</th>
              <th className="pb-2 pr-4 text-right">成交价</th>
              <th className="pb-2 text-right">手续费</th>
            </tr>
          </thead>
          <tbody>
            {trades.map(trade => (
              <tr key={trade.order_id} className="border-b last:border-0">
                <td className="py-2 pr-4 text-gray-500">
                  {trade.filled_at ? new Date(trade.filled_at).toLocaleString('zh-CN') : '-'}
                </td>
                <td className="py-2 pr-4 font-mono">{trade.asset_id}</td>
                <td className={cn('py-2 pr-4', trade.side === 'buy' ? 'text-red-600' : 'text-green-600')}>
                  {trade.side === 'buy' ? '买入' : '卖出'}
                </td>
                <td className="py-2 pr-4 text-right">{trade.filled_qty?.toLocaleString() ?? '-'}</td>
                <td className="py-2 pr-4 text-right">{trade.filled_price?.toFixed(2) ?? '-'}</td>
                <td className="py-2 text-right">{trade.commission?.toFixed(2) ?? '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

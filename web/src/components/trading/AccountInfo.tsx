import { useQuery } from '@tanstack/react-query'
import { tradingApi } from '@/lib/api/trading'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { cn } from '@/lib/utils'

interface Props {
  broker?: string
}

export function AccountInfo({ broker = 'paper' }: Props) {
  const { data: account, isLoading, error } = useQuery({
    queryKey: extendedQueryKeys.trading.account(broker),
    queryFn: () => tradingApi.account(broker),
    refetchInterval: 30000,
  })

  if (isLoading) return <div className="card text-center py-4 text-gray-500">加载中...</div>
  if (error) return <div className="card text-center py-4 text-red-500">加载失败</div>
  if (!account) return null

  return (
    <div className="card">
      <h3 className="font-medium text-gray-800 mb-4">账户信息</h3>
      <div className="grid grid-cols-4 gap-4">
        <div className="text-center">
          <div className="text-sm text-gray-500">总资产</div>
          <div className="text-xl font-semibold">{account.nav.toFixed(2)}</div>
        </div>
        <div className="text-center">
          <div className="text-sm text-gray-500">可用资金</div>
          <div className="text-xl font-semibold">{account.cash.toFixed(2)}</div>
        </div>
        <div className="text-center">
          <div className="text-sm text-gray-500">持仓数</div>
          <div className="text-xl font-semibold">{account.positions_count}</div>
        </div>
        <div className="text-center">
          <div className="text-sm text-gray-500">今日盈亏</div>
          <div className={cn('text-xl font-semibold', account.realized_pnl >= 0 ? 'text-red-600' : 'text-green-600')}>
            {account.realized_pnl >= 0 ? '+' : ''}{account.realized_pnl.toFixed(2)}
          </div>
        </div>
      </div>
    </div>
  )
}

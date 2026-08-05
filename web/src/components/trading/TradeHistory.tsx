import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { tradingApi } from '@/lib/api/trading'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { cn } from '@/lib/utils'

interface Props {
  broker?: string
}

export function TradeHistory({ broker = 'paper' }: Props) {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: extendedQueryKeys.trading.fills(broker),
    queryFn: () => tradingApi.fills(broker),
    refetchInterval: 10000,
  })

  if (isLoading) return <div className="card text-center py-4 text-gray-500">{t('common.loading')}</div>
  if (error) return <div className="card text-center py-4 text-red-500">{t('component.trading.shared.loading_failed')}</div>
  const trades = data?.items ?? []
  if (!trades.length) return <div className="card text-center py-8 text-gray-400">{t('component.trading.trade_history.empty')}</div>

  return (
    <div className="card">
      <h3 className="font-medium text-gray-800 mb-4">{t('component.trading.trade_history.title')}</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="pb-2 pr-4">{t('component.trading.shared.col_time')}</th>
              <th className="pb-2 pr-4">{t('component.trading.shared.col_symbol')}</th>
              <th className="pb-2 pr-4">{t('component.trading.shared.col_side')}</th>
              <th className="pb-2 pr-4 text-right">{t('component.trading.shared.col_filled_qty')}</th>
              <th className="pb-2 pr-4 text-right">{t('component.trading.shared.col_filled_price')}</th>
              <th className="pb-2 text-right">{t('component.trading.shared.col_commission')}</th>
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
                  {trade.side === 'buy' ? t('component.trading.shared.side_buy') : t('component.trading.shared.side_sell')}
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

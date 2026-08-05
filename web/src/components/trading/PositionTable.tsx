import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { tradingApi, type TradePosition } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'

interface PositionTableProps {
  broker?: string
}

export function PositionTable({ broker = 'paper' }: PositionTableProps) {
  const { t } = useTranslation()
  const { data, isLoading } = useQuery({
    queryKey: extendedQueryKeys.trading.positions(broker),
    queryFn: () => tradingApi.positions(broker),
    refetchInterval: 5000,
  })

  if (isLoading) {
    return <div className="card text-gray-400">{t('component.trading.position_table.loading')}</div>
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="card">
        <h2 className="font-semibold text-gray-800 mb-2">{t('component.trading.position_table.title')}</h2>
        <p className="text-gray-400 text-sm">{t('component.trading.position_table.empty')}</p>
      </div>
    )
  }

  return (
    <div className="card">
      <h2 className="font-semibold text-gray-800 mb-4">
        {t('component.trading.position_table.title')} <span className="text-sm font-normal text-gray-400">({data.total})</span>
      </h2>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="pb-2 pr-4">{t('component.trading.shared.col_asset')}</th>
              <th className="pb-2 pr-4 text-right">{t('component.trading.shared.col_qty')}</th>
              <th className="pb-2 pr-4 text-right">{t('component.trading.position_table.col_cost')}</th>
              <th className="pb-2 pr-4 text-right">{t('component.trading.position_table.col_market_value')}</th>
              <th className="pb-2 text-right">{t('component.trading.position_table.col_pnl')}</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((pos: TradePosition) => {
              const pnlSign = pos.unrealized_pnl >= 0 ? '+' : ''
              const pnlColor = pos.unrealized_pnl >= 0 ? 'text-red-600' : 'text-green-600'
              return (
                <tr key={pos.asset_id} className="border-b last:border-0">
                  <td className="py-2 pr-4 font-mono">{pos.asset_id}</td>
                  <td className="py-2 pr-4 text-right">{pos.qty.toLocaleString()}</td>
                  <td className="py-2 pr-4 text-right">{pos.avg_cost.toFixed(2)}</td>
                  <td className="py-2 pr-4 text-right">{pos.market_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                  <td className={`py-2 text-right ${pnlColor}`}>
                    {pnlSign}{pos.unrealized_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}
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

import { useQuery } from '@tanstack/react-query'
import { liveApi } from '@/lib/api/live'

interface PositionPnLProps {
  deploymentId: string
}

export function PositionPnL({ deploymentId }: PositionPnLProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['live', 'positions', deploymentId],
    queryFn: () => liveApi.positions(deploymentId),
    refetchInterval: 10_000,
    enabled: !!deploymentId,
  })

  if (isLoading) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-4">持仓盈亏</h3>
        <div className="text-gray-400 text-sm">加载中...</div>
      </div>
    )
  }

  if (!data?.items || data.items.length === 0) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-4">持仓盈亏</h3>
        <div className="text-center text-gray-400 py-8">暂无持仓</div>
      </div>
    )
  }

  return (
    <div className="card">
      <h3 className="font-semibold text-gray-800 mb-4">
        持仓盈亏
        <span className="text-sm font-normal text-gray-400 ml-2">({data.items.length})</span>
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-gray-50">
            <tr>
              <th className="table-th">资产</th>
              <th className="table-th text-right">数量</th>
              <th className="table-th text-right">成本价</th>
              <th className="table-th text-right">现价</th>
              <th className="table-th text-right">盈亏</th>
              <th className="table-th text-right">盈亏%</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((pos: Record<string, unknown>) => {
              const pnl = Number(pos.pnl ?? pos.unrealized_pnl ?? 0)
              const pnlPct = Number(pos.pnl_pct ?? pos.unrealized_pnl_pct ?? 0)
              const pnlColor = pnl >= 0 ? 'text-red-600' : 'text-green-600'
              const posKey = String(pos.asset_id ?? pos.symbol ?? pos.id ?? Math.random())

              return (
                <tr key={posKey} className="table-row">
                  <td className="table-td font-mono">
                    {String(pos.asset_id ?? pos.ticker ?? '--')}
                  </td>
                  <td className="table-td text-right">
                    {Number(pos.quantity ?? pos.qty ?? 0).toLocaleString()}
                  </td>
                  <td className="table-td text-right">
                    {Number(pos.cost_price ?? pos.avg_cost ?? 0).toFixed(2)}
                  </td>
                  <td className="table-td text-right">
                    {Number(pos.current_price ?? pos.price ?? 0).toFixed(2)}
                  </td>
                  <td className={`table-td text-right font-medium ${pnlColor}`}>
                    {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                  </td>
                  <td className={`table-td text-right font-medium ${pnlColor}`}>
                    {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
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

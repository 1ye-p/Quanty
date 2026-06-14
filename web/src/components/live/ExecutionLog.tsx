import { useQuery } from '@tanstack/react-query'
import { liveApi, type LiveExecution } from '@/lib/api/live'

interface ExecutionLogProps {
  deploymentId: string
}

export function ExecutionLog({ deploymentId }: ExecutionLogProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['live', 'executions', deploymentId],
    queryFn: () => liveApi.getExecutions(deploymentId, 50),
    refetchInterval: 10_000,
    enabled: !!deploymentId,
  })

  if (isLoading) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-4">执行日志</h3>
        <div className="text-gray-400 text-sm">加载中...</div>
      </div>
    )
  }

  if (!data?.items || data.items.length === 0) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-4">执行日志</h3>
        <div className="text-center text-gray-400 py-8">
          <div className="text-3xl mb-2">📋</div>
          <div>暂无执行记录</div>
          <p className="text-xs mt-1">策略执行后会在此显示订单记录</p>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800">
          执行日志
          <span className="text-xs text-gray-500 ml-2">共 {data.total} 条</span>
        </h3>
      </div>

      <div className="max-h-96 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
              <th className="table-th">时间</th>
              <th className="table-th">资产</th>
              <th className="table-th">方向</th>
              <th className="table-th text-right">数量</th>
              <th className="table-th text-right">成交价</th>
              <th className="table-th text-right">费用</th>
              <th className="table-th">状态</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((ex: LiveExecution) => (
              <tr key={ex.execution_id} className="table-row">
                <td className="table-td text-gray-400">
                  {ex.executed_at?.slice(0, 16) ?? '--'}
                </td>
                <td className="table-td font-mono">{ex.asset_id}</td>
                <td className="table-td">
                  <span
                    className={`badge ${
                      ex.side === 'buy'
                        ? 'bg-red-100 text-red-800'
                        : 'bg-green-100 text-green-800'
                    }`}
                  >
                    {ex.side === 'buy' ? '买入' : '卖出'}
                  </span>
                </td>
                <td className="table-td text-right">
                  {ex.filled_qty.toLocaleString()}
                </td>
                <td className="table-td text-right">
                  {ex.filled_price.toFixed(2)}
                </td>
                <td className="table-td text-right text-gray-500">
                  {ex.total_cost.toFixed(2)}
                </td>
                <td className="table-td">
                  <span
                    className={`badge ${
                      ex.status === 'filled'
                        ? 'bg-green-100 text-green-800'
                        : ex.status === 'rejected'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {ex.status === 'filled'
                      ? '已成交'
                      : ex.status === 'rejected'
                        ? '已拒绝'
                        : ex.status}
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

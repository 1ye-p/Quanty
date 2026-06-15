import type { Strategy } from '@/lib/types'

interface StrategyTableProps {
  strategies: Strategy[]
  isLoading: boolean
  onEdit: (strategy: Strategy) => void
  onBacktest: (strategy: Strategy) => void
  onDelete: (strategyId: string) => void
}

export function StrategyTable({
  strategies,
  isLoading,
  onEdit,
  onBacktest,
  onDelete,
}: StrategyTableProps) {
  if (isLoading) {
    return <p className="text-gray-400">Loading...</p>
  }

  if (strategies.length === 0) {
    return (
      <div className="text-center text-gray-400 py-12">
        暂无策略，点击"新建策略"开始
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {strategies.map(s => (
        <div key={s.strategy_id} className="card">
          <div className="flex items-start justify-between">
            <div>
              <div className="font-semibold text-gray-900">{s.strategy_id}</div>
              <div className="text-xs text-gray-400 mt-1">
                更新于 {s.updated_at?.slice(0, 16) ?? '---'}
              </div>
            </div>
            <div className="flex gap-2">
              <button
                className="btn-secondary text-xs px-3 py-1 text-green-600 border-green-300 hover:bg-green-50"
                onClick={() => onBacktest(s)}
              >
                ▶ 回测
              </button>
              <button
                className="btn-secondary text-xs px-3 py-1"
                onClick={() => onEdit(s)}
              >
                编辑
              </button>
              <button
                className="btn-danger text-xs px-3 py-1"
                onClick={() => onDelete(s.strategy_id)}
              >
                删除
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

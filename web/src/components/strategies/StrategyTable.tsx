import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation()
  if (isLoading) {
    return <p className="text-gray-400">{t('common.loading')}</p>
  }

  if (strategies.length === 0) {
    return (
      <div className="text-center text-gray-400 py-12">
        {t('component.strategies.strategy_table.empty')}
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
                {t('component.strategies.strategy_table.updated_at', { date: s.updated_at?.slice(0, 16) ?? '---' })}
              </div>
            </div>
            <div className="flex gap-2">
              <button
                className="btn-secondary text-xs px-3 py-1 text-green-600 border-green-300 hover:bg-green-50"
                onClick={() => onBacktest(s)}
              >
                ▶ {t('component.strategies.strategy_table.backtest')}
              </button>
              <button
                className="btn-secondary text-xs px-3 py-1"
                onClick={() => onEdit(s)}
              >
                {t('common.edit')}
              </button>
              <button
                className="btn-danger text-xs px-3 py-1"
                onClick={() => onDelete(s.strategy_id)}
              >
                {t('common.delete')}
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

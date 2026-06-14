/**
 * Experiment display card.
 * Shows experiment ID, model name, status, and key metrics.
 */
import { StatusBadge } from '@/components/ui/StatusBadge'

interface ExperimentCardProps {
  runId: string
  trainerName?: string
  targetName?: string
  status: string
  rmse?: number
  sharpe?: number
  startedAt?: number | string
  selected?: boolean
  onClick?: () => void
}

export function ExperimentCard({
  runId, trainerName, targetName, status, rmse, sharpe, startedAt, selected, onClick,
}: ExperimentCardProps) {
  const formattedTime = typeof startedAt === 'number'
    ? new Date(startedAt).toISOString().slice(0, 16)
    : String(startedAt ?? '').slice(0, 16)

  return (
    <div
      onClick={onClick}
      className={`p-3 rounded-lg cursor-pointer transition-all border ${
        selected ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300 bg-white'
      }`}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-xs text-gray-700">{runId.slice(0, 12)}...</span>
        <StatusBadge status={status?.toLowerCase() ?? 'unknown'} />
      </div>
      <div className="text-sm font-medium text-gray-900">{trainerName || '--'}</div>
      <div className="text-xs text-gray-500 font-mono">{targetName || '--'}</div>
      <div className="flex items-center gap-3 mt-2 text-xs">
        {rmse != null && (
          <span className="text-gray-600">RMSE: <span className="font-mono">{rmse.toFixed(4)}</span></span>
        )}
        {sharpe != null && (
          <span className="text-gray-600">Sharpe: <span className="font-mono">{sharpe.toFixed(3)}</span></span>
        )}
      </div>
      <div className="text-[10px] text-gray-400 mt-1">{formattedTime}</div>
    </div>
  )
}

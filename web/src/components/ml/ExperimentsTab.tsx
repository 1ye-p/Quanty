/**
 * ML experiments table with search, filter, and selection.
 */
import { useState, useMemo, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { mlApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { TrainingCurve } from './TrainingCurve'
import { WalkForwardFolds } from './WalkForwardFolds'
import { PredictionDistribution } from './PredictionDistribution'

interface ExperimentsTabProps {
  selectedRun: string | null
  onSelectRun: (runId: string | null) => void
  compareRuns: string[]
  onToggleCompare: (runId: string) => void
  onCreateStrategy?: (runId: string, modelId: string) => void
}

export function ExperimentsTab({
  selectedRun,
  onSelectRun,
  compareRuns,
  onToggleCompare,
  onCreateStrategy,
}: ExperimentsTabProps) {
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [diagModelId, setDiagModelId] = useState<string | null>(null)

  const { data: diagnostics, isLoading: diagLoading } = useQuery({
    queryKey: extendedQueryKeys.ml.diagnostics(diagModelId ?? ''),
    queryFn: () => mlApi.getModelDiagnostics(diagModelId!),
    enabled: !!diagModelId,
  })

  const { data: experiments, isLoading } = useQuery({
    queryKey: extendedQueryKeys.ml.experiments(50),
    queryFn: () => mlApi.experiments(50),
  })

  const filtered = useMemo(() => {
    if (!experiments?.items) return []
    return experiments.items.filter(r => {
      const matchStatus = statusFilter === 'all' || r.status === statusFilter
      const q = search.toLowerCase()
      const matchSearch = !q
        || r.run_id.toLowerCase().includes(q)
        || (r.trainer_name ?? '').toLowerCase().includes(q)
        || (r.target_name ?? '').toLowerCase().includes(q)
      return matchStatus && matchSearch
    })
  }, [experiments, search, statusFilter])

  // Clear selectedRun when filtered out
  useEffect(() => {
    if (selectedRun && !filtered.some(r => r.run_id === selectedRun)) {
      onSelectRun(null)
    }
  }, [filtered, selectedRun, onSelectRun])

  return (
    <div>
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <h2 className="font-semibold text-gray-800">
          Experiments ({filtered.length}
          {(search || statusFilter !== 'all')
            ? ` / ${experiments?.items?.length ?? 0} (this page)`
            : filtered.length !== (experiments?.total ?? 0)
              ? ` / ${experiments?.total ?? 0}` : ''})
        </h2>
        <div className="ml-auto flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="text-xs border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="all">All Status</option>
            <option value="completed">Completed</option>
            <option value="running">Running</option>
            <option value="error">Failed</option>
            <option value="pending">Pending</option>
          </select>
          <div className="relative">
            <input
              type="text"
              placeholder="Search run_id / trainer / target..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-6 pr-6 py-1 text-xs border rounded focus:outline-none focus:ring-1 focus:ring-brand-500 w-48"
            />
            <span className="absolute left-1.5 top-1/2 -translate-y-1/2 text-gray-400 text-xs">🔍</span>
            {search && (
              <button onClick={() => setSearch('')}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs">✕</button>
            )}
          </div>
        </div>
      </div>

      {isLoading && <p className="text-gray-400">Loading...</p>}
      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              {['', 'Run ID', 'Trainer', 'Target', 'Status', 'RMSE', 'Sharpe', 'Started', 'Actions'].map(h => (
                <th key={h} className="table-th">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!filtered.length && (
              <tr><td colSpan={9} className="table-td text-center text-gray-400 py-8">
                {search || statusFilter !== 'all' ? 'No matching experiments' : 'No experiment records'}
              </td></tr>
            )}
            {filtered.map(r => (
              <tr key={r.run_id}
                className={`table-row cursor-pointer ${selectedRun === r.run_id ? 'bg-blue-50' : ''}`}
                onClick={() => onSelectRun(r.run_id)}>
                <td className="table-td" onClick={e => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={compareRuns.includes(r.run_id)}
                    onChange={e => { e.stopPropagation(); onToggleCompare(r.run_id) }}
                  />
                </td>
                <td className="table-td font-mono text-xs">{r.run_id.slice(0, 8)}...</td>
                <td className="table-td">{r.trainer_name || r.params?.trainer_name || '--'}</td>
                <td className="table-td text-xs font-mono">{r.target_name || '--'}</td>
                <td className="table-td">
                  <StatusBadge status={r.status?.toLowerCase() ?? 'unknown'} />
                  {r.status === 'error' && r.error_text && (
                    <span className="block text-xs text-red-500 mt-0.5 max-w-[180px] truncate" title={r.error_text}>
                      {r.error_text.slice(0, 40)}
                    </span>
                  )}
                </td>
                <td className="table-td">{r.metrics?.rmse?.toFixed(4) ?? '--'}</td>
                <td className="table-td">{r.metrics?.sharpe?.toFixed(3) ?? '--'}</td>
                <td className="table-td text-gray-400 text-xs">
                  {typeof r.started_at === 'number' ? new Date(r.started_at).toISOString().slice(0, 16) : String(r.started_at ?? '').slice(0, 16)}
                </td>
                <td className="table-td" onClick={e => e.stopPropagation()}>
                  <div className="flex items-center gap-1">
                    {(r.status === 'completed' || r.status === 'done') && r.model_id && (
                      <button
                        className="text-xs text-brand-600 hover:text-brand-800 hover:underline"
                        onClick={() => setDiagModelId(diagModelId === r.model_id ? null : r.model_id!)}
                      >
                        {diagModelId === r.model_id ? 'Hide Diagnostics' : 'Diagnostics'}
                      </button>
                    )}
                    {(r.status === 'completed' || r.status === 'done') && r.model_id && onCreateStrategy && (
                      <button
                        className="btn-secondary text-xs"
                        onClick={() => onCreateStrategy(r.run_id, r.model_id!)}
                      >
                        Create Strategy
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Diagnostics expandable panel */}
      {diagModelId && (
        <div className="card mt-3 p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-800">
              Diagnostics &mdash; <span className="font-mono text-sm text-gray-500">{diagModelId}</span>
            </h3>
            <button
              className="text-gray-400 hover:text-gray-600 text-lg leading-none"
              onClick={() => setDiagModelId(null)}
              title="Close"
            >
              &#x2715;
            </button>
          </div>

          {diagLoading && (
            <p className="text-gray-400 text-sm py-8 text-center">Loading diagnostics...</p>
          )}

          {!diagLoading && diagnostics && (
            <div className="grid gap-4">
              <TrainingCurve data={diagnostics.training_curve} />
              <div className="grid md:grid-cols-2 gap-4">
                <WalkForwardFolds folds={diagnostics.walk_forward_stability} />
                <PredictionDistribution bins={diagnostics.prediction_distribution} />
              </div>
            </div>
          )}

          {!diagLoading && !diagnostics && (
            <p className="text-gray-400 text-sm py-8 text-center">No diagnostics data available.</p>
          )}
        </div>
      )}
    </div>
  )
}

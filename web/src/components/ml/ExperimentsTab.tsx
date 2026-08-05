/**
 * ML experiments table with search, filter, and selection.
 */
import { useState, useMemo, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [diagModelId, setDiagModelId] = useState<string | null>(null)

  const { data: diagnostics, isLoading: diagLoading, error: diagError } = useQuery({
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
          {t('component.ml.experiments_tab.title_count', { filtered: filtered.length })}
          {(search || statusFilter !== 'all')
            ? t('component.ml.experiments_tab.title_page', { count: experiments?.items?.length ?? 0 })
            : filtered.length !== (experiments?.total ?? 0)
              ? t('component.ml.experiments_tab.title_total', { total: experiments?.total ?? 0 }) : ''}
          )
        </h2>
        <div className="ml-auto flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="text-xs border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="all">{t('component.ml.experiments_tab.status_all')}</option>
            <option value="completed">{t('component.ml.experiments_tab.status_completed')}</option>
            <option value="running">{t('component.ml.experiments_tab.status_running')}</option>
            <option value="error">{t('component.ml.experiments_tab.status_failed')}</option>
            <option value="pending">{t('component.ml.experiments_tab.status_pending')}</option>
          </select>
          <div className="relative">
            <input
              type="text"
              placeholder={t('component.ml.experiments_tab.ph_search')}
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

      {isLoading && <p className="text-gray-400">{t('component.ml.experiments_tab.loading')}</p>}
      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              {['', t('component.ml.experiments_tab.th_run_id'), t('component.ml.experiments_tab.th_trainer'), t('component.ml.experiments_tab.th_target'), t('component.ml.experiments_tab.th_status'), t('component.ml.experiments_tab.th_rmse'), t('component.ml.experiments_tab.th_sharpe'), t('component.ml.experiments_tab.th_started'), t('component.ml.experiments_tab.th_actions')].map((h, i) => (
                <th key={i} className="table-th">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!filtered.length && (
              <tr><td colSpan={9} className="table-td text-center text-gray-400 py-8">
                {search || statusFilter !== 'all' ? t('component.ml.experiments_tab.empty_filtered') : t('component.ml.experiments_tab.empty_default')}
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
                        {diagModelId === r.model_id ? t('component.ml.experiments_tab.diag_hide') : t('component.ml.experiments_tab.diag_show')}
                      </button>
                    )}
                    {(r.status === 'completed' || r.status === 'done') && r.model_id && onCreateStrategy && (
                      <button
                        className="btn-secondary text-xs"
                        onClick={() => onCreateStrategy(r.run_id, r.model_id!)}
                      >
                        {t('component.ml.experiments_tab.btn_create_strategy')}
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
              {t('component.ml.experiments_tab.diag_title')} &mdash; <span className="font-mono text-sm text-gray-500">{diagModelId}</span>
            </h3>
            <button
              className="text-gray-400 hover:text-gray-600 text-lg leading-none"
              onClick={() => setDiagModelId(null)}
              title={t('component.ml.experiments_tab.close')}
            >
              &#x2715;
            </button>
          </div>

          {diagLoading && (
            <p className="text-gray-400 text-sm py-8 text-center">{t('component.ml.experiments_tab.diag_loading')}</p>
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

          {!diagLoading && diagError && (
            <p className="text-red-500 text-sm py-8 text-center">{t('component.ml.experiments_tab.diag_failed', { message: (diagError as Error).message })}</p>
          )}

          {!diagLoading && !diagnostics && !diagError && (
            <p className="text-gray-400 text-sm py-8 text-center">{t('component.ml.experiments_tab.diag_empty')}</p>
          )}
        </div>
      )}
    </div>
  )
}

import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery } from '@tanstack/react-query'
import { backtestsApi } from '@/lib/api'
import { SensitivityHeatmap } from './SensitivityHeatmap'
import { SensitivityDetail } from './SensitivityDetail'

interface SensitivityPanelProps {
  runId: string
  onComplete?: (result: any) => void
}

function exportToCSV(data: Record<string, any>[], filename: string) {
  if (!data || data.length === 0) return
  const headers = Object.keys(data[0])
  const escCSV = (v: unknown) => {
    const s = String(v ?? '')
    return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s.replace(/"/g, '""')}"` : s
  }
  const rows = data.map(row => headers.map(h => escCSV(row[h])).join(','))
  const csv = [headers.join(','), ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function SensitivityPanel({ runId, onComplete }: SensitivityPanelProps) {
  const { t } = useTranslation()
  const [paramName, setParamName] = useState('top_n')
  const [paramValues, setParamValues] = useState('5, 10, 15, 20')
  const [primaryMetric, setPrimaryMetric] = useState('sharpe_ratio')
  const [jobId, setJobId] = useState<string | null>(null)
  const [selectedCell, setSelectedCell] = useState<{
    x: string
    y: string
    metrics: Record<string, number>
  } | null>(null)

  const mutation = useMutation({
    mutationFn: () => {
      const values = paramValues.split(',').map(v => {
        const n = Number(v.trim())
        return isNaN(n) ? v.trim() : n
      })
      return backtestsApi.runSensitivity(runId, {
        param_grid: { [paramName]: values },
        primary_metric: primaryMetric,
      })
    },
    onSuccess: (data) => {
      setJobId(data.job_id)
    },
  })

  // Poll for results
  const { data: result } = useQuery({
    queryKey: ['sensitivity-result', runId, jobId],
    queryFn: () => backtestsApi.getSensitivityResult(runId, jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data
      if (data?.status === 'completed' || data?.status === 'failed') return false
      return 2000
    },
  })

  // History query
  const { data: history } = useQuery({
    queryKey: ['sensitivity-history', runId],
    queryFn: () => backtestsApi.getSensitivityHistory(runId),
    enabled: !!runId,
  })

  const isRunning = mutation.isPending || (result?.status === 'running')
  const isComplete = result?.status === 'completed'
  const isFailed = result?.status === 'failed'

  // Invoke onComplete callback when results arrive
  useEffect(() => {
    if (isComplete && result?.result && onComplete) {
      onComplete(result.result)
    }
  }, [isComplete, result?.result, onComplete])

  return (
    <div className="card space-y-4">
      <h3 className="font-semibold text-gray-900">{t('component.backtests.sensitivity.title')}</h3>

      {/* Configuration */}
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t('component.backtests.sensitivity.label.param_name')}</label>
          <select
            value={paramName}
            onChange={e => setParamName(e.target.value)}
            className="input-field text-sm w-full"
          >
            <option value="top_n">top_n</option>
            <option value="rebalance_frequency">rebalance_frequency</option>
            <option value="stop_loss">stop_loss</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t('component.backtests.sensitivity.label.param_values')}</label>
          <input
            type="text"
            value={paramValues}
            onChange={e => setParamValues(e.target.value)}
            className="input-field text-sm w-full"
            placeholder="5, 10, 15, 20"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t('component.backtests.sensitivity.label.metric')}</label>
          <select
            value={primaryMetric}
            onChange={e => setPrimaryMetric(e.target.value)}
            className="input-field text-sm w-full"
          >
            <option value="sharpe_ratio">{t('component.backtests.sensitivity.metric_option.sharpe_ratio')}</option>
            <option value="total_return">{t('component.backtests.sensitivity.metric_option.total_return')}</option>
            <option value="max_drawdown">{t('component.backtests.sensitivity.metric_option.max_drawdown')}</option>
          </select>
        </div>
      </div>

      {/* Action */}
      <div className="flex gap-2">
        <button
          onClick={() => mutation.mutate()}
          disabled={isRunning || !paramValues.trim()}
          className="btn-primary disabled:opacity-50"
        >
          {isRunning ? t('common.running') : t('component.backtests.sensitivity.btn.run_scan')}
        </button>
        {isComplete && result?.result?.summary && (
          <button
            onClick={() => exportToCSV(result.result.summary, `sensitivity_${runId}_${paramName}.csv`)}
            className="btn-secondary text-sm"
          >
            {t('component.backtests.sensitivity.btn.export_csv')}
          </button>
        )}
      </div>

      {/* Status */}
      {isRunning && (
        <div className="text-sm text-blue-600">{t('component.backtests.sensitivity.status.running')}</div>
      )}
      {isFailed && (
        <div className="text-sm text-red-600">{t('component.backtests.sensitivity.status.failed', { error: result?.error })}</div>
      )}
      {isComplete && result?.result && onComplete && (
        <div className="text-sm text-green-600">{t('component.backtests.sensitivity.status.complete')}</div>
      )}

      {/* Heatmap */}
      {isComplete && result?.result?.summary && result.result.summary.length >= 2 && (
        <SensitivityHeatmap
          data={result.result.summary}
          paramX={paramName}
          paramY={Object.keys(result.result.param_grid || {}).find(k => k !== paramName) || paramName}
          metricKey={result.result.primary_metric || primaryMetric}
          onCellClick={(x, y, metrics) => setSelectedCell({ x, y, metrics })}
        />
      )}

      {/* Detail panel */}
      {selectedCell && (
        <SensitivityDetail
          paramX={paramName}
          paramXValue={selectedCell.x}
          paramY={Object.keys(result?.result?.param_grid || {}).find(k => k !== paramName) || paramName}
          paramYValue={selectedCell.y}
          metrics={selectedCell.metrics}
          onClose={() => setSelectedCell(null)}
        />
      )}

      {/* History list */}
      {history?.history && history.history.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-gray-700">{t('component.backtests.sensitivity.history.title')}</h4>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {history.history.map((h) => (
              <div
                key={h.job_id}
                className="flex items-center justify-between text-xs px-2 py-1.5 rounded bg-gray-50 hover:bg-gray-100"
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-block w-2 h-2 rounded-full ${
                      h.status === 'completed'
                        ? 'bg-green-500'
                        : h.status === 'failed'
                        ? 'bg-red-500'
                        : 'bg-blue-500 animate-pulse'
                    }`}
                  />
                  <span className="font-mono text-gray-600">
                    {h.job_id.slice(0, 8)}...
                  </span>
                </div>
                <div className="flex items-center gap-3 text-gray-500">
                  <span>{new Date(h.created_at).toLocaleString()}</span>
                  {h.status === 'failed' && h.error && (
                    <span className="text-red-500 truncate max-w-32" title={h.error}>
                      {h.error}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * IC analysis results display.
 * Shows IC summary metrics, IC time series chart, and quantile returns.
 */
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { factorAnalyticsApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'

interface ICAnalysisTabProps {
  selectedFactor: string
  featureSetVersion: string
}

export function ICAnalysisTab({ selectedFactor, featureSetVersion }: ICAnalysisTabProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeJobId = searchParams.get('ic_job')
  const [horizonDays, setHorizonDays] = useState(1)

  const computeMutation = useMutation({
    mutationFn: (params: { factor_name: string; feature_set_version: string }) =>
      factorAnalyticsApi.computeIC({ ...params, horizon_days: horizonDays }),
    onSuccess: (data) => {
      setSearchParams(prev => { prev.set('ic_job', data.job_id); return prev }, { replace: true })
    },
  })

  const { data: jobResult } = useQuery({
    queryKey: extendedQueryKeys.factorAnalytics.icJob(activeJobId ?? ''),
    queryFn: () => factorAnalyticsApi.icJob(activeJobId as string),
    enabled: !!activeJobId,
    refetchInterval: (query) => {
      const d = query.state.data
      return d && (d.status === 'done' || d.status === 'error') ? false : 2000
    },
  })

  const icSeries = jobResult?.status === 'done' ? (jobResult.series_json ?? []) : []
  const icSummary = jobResult?.summary_json

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold text-gray-900">IC Analysis: {selectedFactor}</h2>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-500">Horizon</label>
            <select
              className="input w-28"
              value={horizonDays}
              onChange={e => setHorizonDays(Number(e.target.value))}
            >
              {[1, 2, 3, 5, 10, 20].map(d => (
                <option key={d} value={d}>{d} days</option>
              ))}
            </select>
          </div>
          <button
            onClick={() => computeMutation.mutate({ factor_name: selectedFactor, feature_set_version: featureSetVersion })}
            disabled={!featureSetVersion || computeMutation.isPending}
            className="btn-primary text-sm"
          >
            {computeMutation.isPending ? 'Submitting...' : 'Compute IC/IR'}
          </button>
        </div>
      </div>

      {activeJobId && jobResult?.status !== 'done' && (
        <p className="text-blue-500 text-sm">Computing... (job: {activeJobId.slice(0, 8)})</p>
      )}

      {jobResult?.status === 'error' && (
        <p className="text-red-500 text-sm">Failed: {(jobResult as Record<string, unknown>)?.error_text as string ?? 'Unknown error'}</p>
      )}

      {icSummary && (
        <div className="grid grid-cols-3 gap-4 mb-4">
          {[
            { label: 'Mean IC', value: icSummary.mean_ic?.toFixed(4) },
            { label: 'IR', value: icSummary.ir?.toFixed(4) },
            { label: 'Hit Rate', value: `${((icSummary.hit_rate ?? 0) * 100).toFixed(1)}%` },
          ].map(({ label, value }) => (
            <div key={label} className="text-center p-3 bg-gray-50 rounded-lg">
              <div className="text-lg font-bold text-brand-600">{value ?? '--'}</div>
              <div className="text-xs text-gray-500">{label}</div>
            </div>
          ))}
        </div>
      )}

      {icSeries.length > 0 && (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={icSeries}>
            <XAxis dataKey="trade_date" tick={{ fontSize: 10 }} />
            <YAxis domain={[-0.3, 0.3]} tick={{ fontSize: 10 }} />
            <Tooltip />
            <ReferenceLine y={0} stroke="#e5e7eb" />
            <Line type="monotone" dataKey="ic" stroke="#4f63d2" dot={false} strokeWidth={1.5} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

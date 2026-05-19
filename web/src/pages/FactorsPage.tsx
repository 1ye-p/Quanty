import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { factorAnalyticsApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { useJobPoller } from '@/hooks/useJobPoller'
import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'

export function FactorsPage() {
  const [selectedFactor, setSelectedFactor] = useState<string | null>(null)
  const [featureSetVersion, setFeatureSetVersion] = useState('')
  const [activeJobId, setActiveJobId] = useState<string | null>(null)

  const { data: defs, isLoading } = useQuery({
    queryKey: extendedQueryKeys.factorAnalytics.definitions(),
    queryFn: factorAnalyticsApi.definitions,
  })

  const { data: versions } = useQuery({
    queryKey: ["factors", "versions"],
    queryFn: async () => {
      const r = await fetch('/api/v1/factors/versions')
      return r.json()
    },
  })

  const computeMutation = useMutation({
    mutationFn: (params: { factor_name: string; feature_set_version: string }) =>
      factorAnalyticsApi.computeIC({ ...params, horizon_days: 1 }),
    onSuccess: (data) => setActiveJobId(data.job_id),
  })

  const { data: jobResult } = useJobPoller({
    queryKey: extendedQueryKeys.factorAnalytics.icJob(activeJobId ?? ''),
    queryFn: () => factorAnalyticsApi.icJob(activeJobId!),
    isDone: (d) => d.status === 'done' || d.status === 'error',
    enabled: !!activeJobId,
  })

  const icSeries = jobResult?.status === 'done' ? (jobResult.series_json ?? []) : []
  const icSummary = jobResult?.summary_json

  return (
    <div>
      <h1 className="page-title">Alpha 因子研究</h1>
      <p className="page-subtitle">浏览内置因子、计算 IC/IR 时间序列</p>

      <div className="flex gap-3 mb-6">
        <select
          className="input max-w-xs"
          value={featureSetVersion}
          onChange={e => setFeatureSetVersion(e.target.value)}
        >
          <option value="">选择 Feature Set 版本</option>
          {versions?.items?.map((v: { feature_set_version: string }) => (
            <option key={v.feature_set_version} value={v.feature_set_version}>
              {v.feature_set_version.slice(0, 16)}…
            </option>
          ))}
        </select>
      </div>

      {isLoading && <p className="text-gray-400">Loading…</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {defs?.items.map(f => (
          <div
            key={f.name}
            onClick={() => {
              const next = selectedFactor === f.name ? null : f.name
              setSelectedFactor(next)
              if (next !== selectedFactor) setActiveJobId(null)   // reset stale IC results
            }}
            className={`card cursor-pointer hover:shadow-md transition-shadow border-2 ${
              selectedFactor === f.name ? 'border-blue-500' : 'border-transparent'
            }`}
          >
            <div className="font-semibold text-gray-900 mb-1">{f.name}</div>
            <div className="text-xs text-gray-500 mb-2">{f.description || '无描述'}</div>
            <div className="flex flex-wrap gap-1">
              {f.tags.map(t => (
                <span key={t} className="badge bg-blue-50 text-blue-700">{t}</span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {selectedFactor && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">IC 分析：{selectedFactor}</h2>
            <button
              onClick={() => computeMutation.mutate({ factor_name: selectedFactor, feature_set_version: featureSetVersion })}
              disabled={!featureSetVersion || computeMutation.isPending}
              className="btn-primary text-sm"
            >
              {computeMutation.isPending ? '提交中…' : '计算 IC/IR'}
            </button>
          </div>

          {activeJobId && jobResult?.status !== 'done' && (
            <p className="text-blue-500 text-sm">计算中… (job: {activeJobId.slice(0, 8)})</p>
          )}

          {jobResult?.status === 'error' && (
            <p className="text-red-500 text-sm">计算失败：{(jobResult as unknown as { error_text?: string }).error_text}</p>
          )}

          {icSummary && (
            <div className="grid grid-cols-3 gap-4 mb-4">
              {[
                { label: '平均 IC', value: icSummary.mean_ic?.toFixed(4) },
                { label: 'IR', value: icSummary.ir?.toFixed(4) },
                { label: '正 IC 占比', value: `${((icSummary.hit_rate ?? 0) * 100).toFixed(1)}%` },
              ].map(({ label, value }) => (
                <div key={label} className="text-center p-3 bg-gray-50 rounded-lg">
                  <div className="text-lg font-bold text-brand-600">{value ?? '—'}</div>
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
      )}
    </div>
  )
}

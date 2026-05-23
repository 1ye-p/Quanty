import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { factorAnalyticsApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { LineChart, Line, BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'

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

  const { data: jobResult } = useQuery({
    queryKey: extendedQueryKeys.factorAnalytics.icJob(activeJobId ?? ''),
    queryFn: () => factorAnalyticsApi.icJob(activeJobId!),
    enabled: !!activeJobId,
    refetchInterval: (query) => {
      const d = query.state.data
      return d && (d.status === 'done' || d.status === 'error') ? false : 2000
    },
  })

  const icSeries = jobResult?.status === 'done' ? (jobResult.series_json ?? []) : []
  const icSummary = jobResult?.summary_json

  return (
    <div>
      <h1 className="page-title">Alpha 因子研究</h1>
      <p className="page-subtitle">浏览内置因子、计算 IC/IR 时间序列</p>

      {/* 流程步骤提示 */}
      <div className="flex items-center gap-2 mb-5 p-3 bg-blue-50 rounded-lg border border-blue-100">
        {[
          { n: 1, label: '选择 Feature Set 版本', done: !!featureSetVersion },
          { n: 2, label: '选择要分析的因子', done: !!selectedFactor },
          { n: 3, label: '点击"计算 IC 分析"', done: icSeries.length > 0 },
        ].map((step, idx, arr) => (
          <div key={step.n} className="flex items-center gap-2">
            <div className={`flex items-center gap-1.5 text-sm font-medium ${
              step.done ? 'text-green-700' : idx === arr.filter(s => s.done).length ? 'text-blue-700' : 'text-gray-400'
            }`}>
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
                step.done ? 'bg-green-600 text-white' : idx === arr.filter(s => s.done).length ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'
              }`}>
                {step.done ? '✓' : step.n}
              </span>
              {step.label}
            </div>
            {idx < arr.length - 1 && <span className="text-gray-300">→</span>}
          </div>
        ))}
      </div>

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

          {icSummary?.rank_ic_decay && icSummary.rank_ic_decay.length > 0 && (
            <div className="card mt-4">
              <h3 className="font-semibold text-gray-800 mb-3 text-sm">Rank IC 衰减（lag 1-10）</h3>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={icSummary.rank_ic_decay} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                  <XAxis dataKey="lag" tick={{ fontSize: 11 }} label={{ value: 'Lag', position: 'insideRight', fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: unknown) => (v as number).toFixed(4)} />
                  <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
                  <Line type="monotone" dataKey="ic" stroke="#3b82f6" dot={{ r: 3 }} strokeWidth={2} name="IC" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {icSummary?.quantile_returns && icSummary.quantile_returns.length > 0 && (
            <div className="card mt-4">
              <h3 className="font-semibold text-gray-800 mb-3 text-sm">分层收益图（5 分组）</h3>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={icSummary.quantile_returns} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                  <XAxis dataKey="quantile" tick={{ fontSize: 11 }} tickFormatter={(v: number) => `Q${v}`} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
                  <Tooltip formatter={(v: unknown) => `${((v as number) * 100).toFixed(3)}%`} />
                  <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
                  <Bar dataKey="mean_return" name="平均收益" radius={[3, 3, 0, 0]}>
                    {icSummary.quantile_returns.map((entry) => (
                      <Cell key={entry.quantile} fill={entry.mean_return >= 0 ? '#22c55e' : '#ef4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {icSummary?.factor_turnover != null && (
            <div className="card mt-4">
              <div className="text-sm text-gray-500 mb-1">因子换手率（Top 20%）</div>
              <div className="text-2xl font-bold text-gray-900">
                {(icSummary.factor_turnover * 100).toFixed(1)}%
              </div>
              <div className="text-xs text-gray-400 mt-1">平均每日顶部资产替换比例</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

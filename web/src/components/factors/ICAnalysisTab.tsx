/**
 * IC analysis results display.
 * Shows IC summary metrics, IC time series chart, and quantile returns.
 */
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { factorAnalyticsApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'

interface ICAnalysisTabProps {
  selectedFactor: string
  featureSetVersion: string
}

export function ICAnalysisTab({ selectedFactor, featureSetVersion }: ICAnalysisTabProps) {
  const { t } = useTranslation()
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
        <h2 className="font-semibold text-gray-900">{t('component.factors.ic_analysis_tab.title', { name: selectedFactor })}</h2>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-500">{t('component.factors.ic_analysis_tab.label_horizon')}</label>
            <select
              className="input w-28"
              value={horizonDays}
              onChange={e => setHorizonDays(Number(e.target.value))}
            >
              {[1, 2, 3, 5, 10, 20].map(d => (
                <option key={d} value={d}>{t('component.factors.ic_analysis_tab.horizon_days', { count: d })}</option>
              ))}
            </select>
          </div>
          <button
            onClick={() => computeMutation.mutate({ factor_name: selectedFactor, feature_set_version: featureSetVersion })}
            disabled={!featureSetVersion || computeMutation.isPending}
            className="btn-primary text-sm"
          >
            {computeMutation.isPending ? t('component.factors.ic_analysis_tab.btn_submitting') : t('component.factors.ic_analysis_tab.btn_compute')}
          </button>
        </div>
      </div>

      {activeJobId && jobResult?.status !== 'done' && (
        <p className="text-blue-500 text-sm">{t('component.factors.ic_analysis_tab.computing_job', { jobId: activeJobId.slice(0, 8) })}</p>
      )}

      {jobResult?.status === 'error' && (
        <p className="text-red-500 text-sm">{t('component.factors.ic_analysis_tab.failed_prefix')} {(jobResult as Record<string, unknown>)?.error_text as string ?? t('component.factors.ic_analysis_tab.failed_unknown')}</p>
      )}

      {icSummary && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-4">
            {[
              { label: t('component.factors.ic_analysis_tab.metric_mean_ic'), value: icSummary.mean_ic?.toFixed(4) },
              { label: t('component.factors.ic_analysis_tab.metric_ir'), value: icSummary.ir?.toFixed(4) },
              { label: t('component.factors.ic_analysis_tab.metric_hit_rate'), value: `${((icSummary.hit_rate ?? 0) * 100).toFixed(1)}%` },
            ].map(({ label, value }) => (
              <div key={label} className="text-center p-3 bg-gray-50 rounded-lg">
                <div className="text-lg font-bold text-brand-600">{value ?? '--'}</div>
                <div className="text-xs text-gray-500">{label}</div>
              </div>
            ))}
          </div>

          {icSummary.ic_ttest && (
            <div className="mb-4 p-3 border border-gray-200 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-gray-700">
                  {t('page.factors.ic_ttest.title')}
                </h3>
                {icSummary.ic_ttest.n < 30 ? (
                  <span className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full">
                    {t('page.factors.ic_ttest.insufficient_sample')}
                  </span>
                ) : icSummary.ic_ttest.significant ? (
                  <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full">
                    {t('page.factors.ic_ttest.significant_yes')}
                  </span>
                ) : (
                  <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full">
                    {t('page.factors.ic_ttest.significant_no')}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div>
                  <div className="text-gray-500">{t('page.factors.ic_ttest.t_stat')}</div>
                  <div className="font-semibold text-gray-900">
                    {icSummary.ic_ttest.t_stat != null ? icSummary.ic_ttest.t_stat.toFixed(3) : '--'}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">{t('page.factors.ic_ttest.p_value')}</div>
                  <div className="font-semibold text-gray-900">
                    {icSummary.ic_ttest.p_value != null ? icSummary.ic_ttest.p_value.toFixed(4) : '--'}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">{t('page.factors.ic_ttest.ci_95')}</div>
                  <div className="font-semibold text-gray-900">
                    {icSummary.ic_ttest.ci_lower != null && icSummary.ic_ttest.ci_upper != null
                      ? `[${icSummary.ic_ttest.ci_lower.toFixed(4)}, ${icSummary.ic_ttest.ci_upper.toFixed(4)}]`
                      : '--'}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">{t('page.factors.ic_ttest.sample_size')}</div>
                  <div className="font-semibold text-gray-900">{icSummary.ic_ttest.n}</div>
                </div>
              </div>
              {icSummary.ic_ttest.n < 30 && (
                <p className="mt-2 text-xs text-amber-600">
                  {t('page.factors.ic_ttest.insufficient_sample_hint')}
                </p>
              )}
            </div>
          )}

          {icSummary.ic_half_life != null && (
            <div className="mb-4 p-3 border border-gray-200 rounded-lg">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">{t('page.factors.half_life.label')}</span>
                <span className="text-sm font-semibold text-brand-600">
                  {t('page.factors.half_life.value', { days: icSummary.ic_half_life })}
                </span>
                <span className="text-xs text-gray-400">{t('page.factors.half_life.hint')}</span>
              </div>
            </div>
          )}

          {icSummary.net_ic != null && icSummary.factor_turnover != null && (
            <div className="mb-4 p-3 border border-gray-200 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-gray-700">
                  {t('page.factors.net_ic.title')}
                </h3>
                <span className="text-xs text-gray-400">{t('page.factors.net_ic.hint')}</span>
              </div>
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div>
                  <div className="text-gray-500">{t('page.factors.net_ic.raw_ic')}</div>
                  <div className="font-semibold text-gray-900">
                    {icSummary.mean_ic != null ? icSummary.mean_ic.toFixed(4) : '--'}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">{t('page.factors.net_ic.turnover')}</div>
                  <div className="font-semibold text-gray-900">
                    {`${(icSummary.factor_turnover * 100).toFixed(1)}%`}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">{t('page.factors.net_ic.net_ic')}</div>
                  <div className="font-semibold text-brand-600">
                    {icSummary.net_ic.toFixed(4)}
                  </div>
                </div>
              </div>
              {icSummary.mean_ic != null && (
                <p className="mt-2 text-xs text-gray-400">
                  {t('page.factors.net_ic.penalty', {
                    delta: (icSummary.mean_ic - icSummary.net_ic).toFixed(4),
                  })}
                </p>
              )}
            </div>
          )}
        </>
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

/**
 * Factor correlation heatmap.
 * Displays pairwise correlations as a colored matrix.
 */
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { factorAnalyticsApi } from '@/lib/api'

interface CorrelationTabProps {
  selectedFactors: string[]
  featureSetVersion: string
}

function corrColor(v: number | null): string {
  if (v === null) return '#f3f4f6'
  const abs = Math.abs(v)
  if (v >= 0) return `oklch(${92 - abs * 45}% 0.12 250)`
  return `oklch(${92 - abs * 45}% 0.12 25)`
}

export function CorrelationTab({ selectedFactors, featureSetVersion }: CorrelationTabProps) {
  const { t } = useTranslation()
  const { data: corrMatrix, isFetching, refetch } = useQuery({
    queryKey: ['factors', 'correlation', selectedFactors, featureSetVersion],
    queryFn: () => factorAnalyticsApi.computeFactorCorrelation({
      factor_names: selectedFactors,
      feature_set_version: featureSetVersion,
    }),
    enabled: false,
  })

  if (selectedFactors.length < 2) {
    return (
      <div className="card">
        <p className="text-sm text-gray-400">{t('component.factors.correlation_tab.empty_min')}</p>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-800">{t('component.factors.correlation_tab.title')}</h3>
        {!corrMatrix ? (
          <button className="btn-secondary text-xs" onClick={() => refetch()}>
            {t('component.factors.correlation_tab.btn_compute')}
          </button>
        ) : isFetching ? (
          <span className="text-xs text-gray-400">{t('component.factors.correlation_tab.computing')}</span>
        ) : null}
      </div>
      {corrMatrix && corrMatrix.factors.length > 0 && (
        <div className="overflow-x-auto">
          <table className="text-xs border-collapse mx-auto">
            <thead>
              <tr>
                <th className="w-20" />
                {corrMatrix.factors.map(f => (
                  <th key={f} className="p-1 text-center font-mono w-14 max-w-[56px] truncate" title={f}>
                    {f.length > 7 ? f.slice(0, 7) + '...' : f}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {corrMatrix.factors.map(f1 => (
                <tr key={f1}>
                  <td className="p-1 font-mono text-right pr-2 text-gray-600 max-w-[80px] truncate" title={f1}>
                    {f1.length > 9 ? f1.slice(0, 9) + '...' : f1}
                  </td>
                  {corrMatrix.factors.map(f2 => {
                    const cell = corrMatrix.matrix.find(c => c.factor_a === f1 && c.factor_b === f2)
                    const v = cell?.correlation ?? null
                    return (
                      <td
                        key={f2}
                        style={{ background: corrColor(v), width: 52, height: 44 }}
                        className="text-center border border-white/50 font-mono"
                        title={`${f1} x ${f2}: ${v !== null ? v.toFixed(3) : 'N/A'}`}
                      >
                        {v !== null ? v.toFixed(2) : '--'}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-gray-400 mt-2 text-center">
            {t('component.factors.correlation_tab.legend')}
          </p>
        </div>
      )}
    </div>
  )
}

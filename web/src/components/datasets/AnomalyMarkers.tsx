import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { datasetsApi } from '@/lib/api'
import { DataState } from '@/components/ui/DataState'

interface AnomalyMarkersProps {
  datasetId: string
}

const TYPE_BADGES: Record<string, { labelKey: string; color: string }> = {
  outlier: { labelKey: 'component.datasets.anomaly.type_outlier', color: 'bg-red-100 text-red-700' },
  missing: { labelKey: 'component.datasets.anomaly.type_missing', color: 'bg-amber-100 text-amber-700' },
  duplicate: { labelKey: 'component.datasets.anomaly.type_duplicate', color: 'bg-orange-100 text-orange-700' },
  invalid: { labelKey: 'component.datasets.anomaly.type_invalid', color: 'bg-purple-100 text-purple-700' },
}

export function AnomalyMarkers({ datasetId }: AnomalyMarkersProps) {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['datasets', datasetId, 'anomalies'],
    queryFn: () => datasetsApi.getAnomalies(datasetId),
    enabled: !!datasetId,
    staleTime: 60_000,
  })

  const anomalies = data?.anomalies ?? []

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-gray-700">{t('component.datasets.anomaly.title')}</h3>

      <DataState isLoading={isLoading} error={error} isEmpty={false} emptyText="">
        {anomalies.length === 0 ? (
          <div className="flex items-center gap-2 p-4 rounded-lg border border-green-200 bg-green-50 text-green-700">
            <span className="text-lg">✓</span>
            <span className="text-sm font-medium">{t('component.datasets.anomaly.none_found')}</span>
          </div>
        ) : (
          <div className="space-y-3">
            {anomalies.map((a, i) => {
              const badge = TYPE_BADGES[a.type]
              const badgeLabel = badge ? t(badge.labelKey) : a.type
              const badgeColor = badge ? badge.color : 'bg-gray-100 text-gray-700'
              return (
                <div key={i} className="p-3 rounded-lg border border-gray-200 bg-white space-y-2">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${badgeColor}`}>
                      {badgeLabel}
                    </span>
                    <span className="text-sm font-mono font-medium text-gray-800">{a.field}</span>
                    <span className="text-xs text-gray-500 ml-auto">{t('component.datasets.anomaly.count_unit', { count: a.count.toLocaleString() })}</span>
                  </div>
                  {a.examples.length > 0 && (
                    <div className="text-xs text-gray-500">
                      {t('component.datasets.anomaly.examples_label')} {a.examples.slice(0, 5).map((ex, j) => (
                        <span key={j} className="inline-block mr-1.5 px-1.5 py-0.5 rounded bg-gray-100 font-mono">
                          {ex}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </DataState>
    </div>
  )
}

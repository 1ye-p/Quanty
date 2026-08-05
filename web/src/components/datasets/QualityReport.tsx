import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { datasetsApi } from '@/lib/api'
import { DataState } from '@/components/ui/DataState'

interface QualityReportProps {
  datasetId: string
}

function scoreColor(score: number): string {
  if (score >= 90) return 'text-green-600'
  if (score >= 70) return 'text-amber-600'
  return 'text-red-600'
}

function scoreBg(score: number): string {
  if (score >= 90) return 'bg-green-50 border-green-200'
  if (score >= 70) return 'bg-amber-50 border-amber-200'
  return 'bg-red-50 border-red-200'
}

function scoreRing(score: number): string {
  if (score >= 90) return 'stroke-green-500'
  if (score >= 70) return 'stroke-amber-500'
  return 'stroke-red-500'
}

export function QualityReport({ datasetId }: QualityReportProps) {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['datasets', datasetId, 'quality-report'],
    queryFn: () => datasetsApi.getQualityReport(datasetId),
    enabled: !!datasetId,
    staleTime: 60_000,
  })

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-gray-700">{t('component.datasets.quality.title')}</h3>

      <DataState isLoading={isLoading} error={error} isEmpty={!data} emptyText={t('component.datasets.quality.empty')}>
        {data && (
          <>
            {/* Score ring + summary */}
            <div className={`flex items-center gap-6 p-4 rounded-lg border ${scoreBg(data.score)}`}>
              <div className="relative w-20 h-20 flex-shrink-0">
                <svg className="w-20 h-20 -rotate-90" viewBox="0 0 36 36">
                  <path
                    className="stroke-gray-200"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    strokeWidth="3"
                  />
                  <path
                    className={scoreRing(data.score)}
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    fill="none"
                    strokeWidth="3"
                    strokeDasharray={`${data.score}, 100`}
                    strokeLinecap="round"
                  />
                </svg>
                <span className={`absolute inset-0 flex items-center justify-center text-lg font-bold ${scoreColor(data.score)}`}>
                  {data.score}
                </span>
              </div>
              <div>
                <div className="text-sm text-gray-600">
                  {t('component.datasets.quality.total_rows')} <strong>{data.total_rows.toLocaleString()}</strong>
                </div>
                <div className="text-sm text-gray-600">
                  {t('component.datasets.quality.total_fields')} <strong>{data.total_fields}</strong>
                </div>
                <div className="text-sm text-gray-600">
                  <strong className={data.issues.length > 0 ? 'text-amber-600' : 'text-green-600'}>{t('component.datasets.quality.issues_found', { count: data.issues.length })}</strong>
                </div>
              </div>
            </div>

            {/* Issues list */}
            {data.issues.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-gray-500 mb-2">{t('component.datasets.quality.issues_list_title')}</h4>
                <div className="overflow-x-auto rounded-lg border border-gray-200">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        {([
                          ['field', 'component.datasets.quality.col.field'],
                          ['issue_type', 'component.datasets.quality.col.issue_type'],
                          ['count', 'component.datasets.quality.col.count'],
                          ['percentage', 'component.datasets.quality.col.percentage'],
                        ] as const).map(([k, key]) => (
                          <th key={k} className="table-th">{t(key)}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {data.issues.map((issue, i) => (
                        <tr key={i} className="table-row">
                          <td className="table-td font-mono text-xs">{issue.field}</td>
                          <td className="table-td">
                            <span className="px-2 py-0.5 rounded text-xs bg-amber-100 text-amber-700">
                              {issue.type}
                            </span>
                          </td>
                          <td className="table-td">{issue.count.toLocaleString()}</td>
                          <td className="table-td">{issue.percentage.toFixed(2)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Suggestions */}
            {data.suggestions.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-gray-500 mb-2">{t('component.datasets.quality.suggestions_title')}</h4>
                <ul className="space-y-1.5">
                  {data.suggestions.map((s, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                      <span className="text-blue-400 mt-0.5 flex-shrink-0">•</span>
                      {s}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </DataState>
    </div>
  )
}

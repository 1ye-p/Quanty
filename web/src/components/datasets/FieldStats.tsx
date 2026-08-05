import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { datasetsApi } from '@/lib/api'
import { DataState } from '@/components/ui/DataState'

interface FieldStatsProps {
  datasetId: string
}

const NULL_RATE_WARN = 0.1

export function FieldStats({ datasetId }: FieldStatsProps) {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: ['datasets', datasetId, 'field-stats'],
    queryFn: () => datasetsApi.getFieldStats(datasetId),
    enabled: !!datasetId,
    staleTime: 60_000,
  })

  const chartData = data?.fields.map(f => ({
    name: f.name,
    nullRate: +(f.null_rate * 100).toFixed(2),
  }))

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-gray-700">{t('component.datasets.field_stats.title')}</h3>

      <DataState isLoading={isLoading} error={error} isEmpty={!data?.fields.length} emptyText={t('component.datasets.field_stats.empty')}>
        {data && (
          <>
            {/* Null rate chart */}
            {chartData && chartData.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-gray-500 mb-2">{t('component.datasets.field_stats.null_rate_chart_title')}</h4>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={chartData} margin={{ top: 4, right: 12, left: -10, bottom: 0 }}>
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 10 }}
                      interval={0}
                      angle={-45}
                      textAnchor="end"
                      height={50}
                    />
                    <YAxis tick={{ fontSize: 10 }} unit="%" />
                    <Tooltip
                      formatter={(v: number) => [`${v}%`, t('component.datasets.field_stats.tooltip_null_rate')]}
                      labelFormatter={v => t('component.datasets.field_stats.tooltip_field', { name: v })}
                    />
                    <Bar dataKey="nullRate" radius={[3, 3, 0, 0]}>
                      {chartData.map((entry, i) => (
                        <Cell
                          key={i}
                          fill={entry.nullRate > NULL_RATE_WARN * 100 ? '#f59e0b' : '#3b82f6'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Stats table */}
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    {([
                      ['field', 'component.datasets.field_stats.col.field'],
                      ['type', 'component.datasets.field_stats.col.type'],
                      ['count', 'component.datasets.field_stats.col.count'],
                      ['null_rate', 'component.datasets.field_stats.col.null_rate'],
                      ['unique', 'component.datasets.field_stats.col.unique'],
                      ['min', 'component.datasets.field_stats.col.min'],
                      ['max', 'component.datasets.field_stats.col.max'],
                      ['mean', 'component.datasets.field_stats.col.mean'],
                      ['std', 'component.datasets.field_stats.col.std'],
                    ] as const).map(([k, key]) => (
                      <th key={k} className="table-th whitespace-nowrap">{t(key)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.fields.map(f => (
                    <tr key={f.name} className="table-row">
                      <td className="table-td font-medium font-mono text-xs">{f.name}</td>
                      <td className="table-td">
                        <span className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 text-xs">
                          {f.type}
                        </span>
                      </td>
                      <td className="table-td">{f.count.toLocaleString()}</td>
                      <td className="table-td">
                        <span className={f.null_rate > NULL_RATE_WARN ? 'text-amber-600 font-medium' : ''}>
                          {(f.null_rate * 100).toFixed(2)}%
                        </span>
                      </td>
                      <td className="table-td">{f.unique_count.toLocaleString()}</td>
                      <td className="table-td font-mono text-xs">{f.min != null ? String(f.min) : '—'}</td>
                      <td className="table-td font-mono text-xs">{f.max != null ? String(f.max) : '—'}</td>
                      <td className="table-td font-mono text-xs">{f.mean != null ? f.mean.toFixed(4) : '—'}</td>
                      <td className="table-td font-mono text-xs">{f.std != null ? f.std.toFixed(4) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </DataState>
    </div>
  )
}

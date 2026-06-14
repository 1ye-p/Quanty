import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { datasetsApi } from '@/lib/api'
import { DataState } from '@/components/ui/DataState'

interface FieldStatsProps {
  datasetId: string
}

const NULL_RATE_WARN = 0.1

export function FieldStats({ datasetId }: FieldStatsProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['datasets', datasetId, 'field-stats'],
    queryFn: () => datasetsApi.getFieldStats(datasetId),
    enabled: !!datasetId,
  })

  const chartData = data?.fields.map(f => ({
    name: f.name,
    nullRate: +(f.null_rate * 100).toFixed(2),
  }))

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-gray-700">字段统计</h3>

      <DataState isLoading={isLoading} error={error} isEmpty={!data?.fields.length} emptyText="暂无字段统计">
        {data && (
          <>
            {/* Null rate chart */}
            {chartData && chartData.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-gray-500 mb-2">空值率分布 (%)</h4>
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
                      formatter={(v: number) => [`${v}%`, '空值率']}
                      labelFormatter={v => `字段: ${v}`}
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
                    {['字段', '类型', '数量', '空值率', '唯一值', '最小值', '最大值', '均值', '标准差'].map(h => (
                      <th key={h} className="table-th whitespace-nowrap">{h}</th>
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

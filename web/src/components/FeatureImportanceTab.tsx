/**
 * FeatureImportanceTab — Bar chart of top-20 feature importances for an ML experiment.
 *
 * Props:
 *   modelVersion — ML experiment run ID
 */
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { mlApi } from '@/lib/api'
import { DataState } from '@/components/ui/DataState'

interface FeatureImportanceTabProps {
  modelVersion: string
}

const TOP_N = 20
const BAR_COLOR = '#6366f1'
const BAR_COLOR_ALT = '#a5b4fc'

export function FeatureImportanceTab({ modelVersion }: FeatureImportanceTabProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['feature-importance', modelVersion],
    queryFn: () => mlApi.featureImportance(modelVersion),
    enabled: !!modelVersion,
    staleTime: 120_000,
  })

  const allItems = data?.items ?? []
  const items = allItems.slice(0, TOP_N)
  const hasMore = allItems.length > TOP_N

  return (
    <DataState
      isLoading={isLoading}
      error={error}
      isEmpty={items.length === 0}
      emptyText="暂无特征重要性数据"
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-700">Top {TOP_N} 特征重要性</h3>
          {hasMore && (
            <span className="text-xs text-gray-400">
              共 {allItems.length} 个特征，展示前 {TOP_N} 个
            </span>
          )}
        </div>

        <ResponsiveContainer width="100%" height={Math.max(400, items.length * 28)}>
          <BarChart
            data={items}
            layout="vertical"
            margin={{ top: 4, right: 24, left: 8, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" horizontal={false} />
            <XAxis
              type="number"
              tick={{ fontSize: 11 }}
              tickFormatter={(v: number) => v.toFixed(3)}
            />
            <YAxis
              type="category"
              dataKey="feature"
              width={140}
              tick={{ fontSize: 11 }}
              tickFormatter={(v: string) =>
                v.length > 20 ? v.slice(0, 18) + '...' : v
              }
            />
            <Tooltip
              formatter={(value: number) => [value.toFixed(4), 'Importance']}
              labelFormatter={(label: string) => `Feature: ${label}`}
            />
            <Bar dataKey="importance" radius={[0, 4, 4, 0]} maxBarSize={22}>
              {items.map((_, idx) => (
                <Cell
                  key={idx}
                  fill={idx % 2 === 0 ? BAR_COLOR : BAR_COLOR_ALT}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        {/* Summary footer */}
        <div className="text-xs text-gray-400 text-right">
          {data?.total != null && `共 ${data.total} 个特征`}
        </div>
      </div>
    </DataState>
  )
}

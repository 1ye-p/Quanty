/**
 * ModelCompareTab — Compare multiple ML models with metrics table and NAV curve overlay.
 *
 * Props:
 *   backtestId     — parent backtest run ID (for context)
 *   selectedModels — array of model IDs to compare
 */
import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { backtestsApi } from '@/lib/api'
import { DataState } from '@/components/ui/DataState'

interface ModelCompareTabProps {
  backtestId: string
  selectedModels: string[]
}

interface CompareRun {
  run_id: string
  strategy_id: string
  engine: string
  status: string
  started_at: string
  dataset_version: string
  metrics: Record<string, number>
  nav_series: { date: string; nav: number }[]
}

const METRIC_DEFS = [
  { key: 'total_return', label: '总收益率', pct: true, invert: false },
  { key: 'annualized_return', label: '年化收益', pct: true, invert: false },
  { key: 'sharpe_ratio', label: 'Sharpe Ratio', pct: false, invert: false },
  { key: 'sortino_ratio', label: 'Sortino Ratio', pct: false, invert: false },
  { key: 'max_drawdown', label: '最大回撤', pct: true, invert: true },
  { key: 'calmar_ratio', label: 'Calmar Ratio', pct: false, invert: false },
  { key: 'win_rate', label: '胜率', pct: true, invert: false },
  { key: 'annualized_volatility', label: '年化波动率', pct: true, invert: true },
  { key: 'profit_factor', label: '盈亏比', pct: false, invert: false },
  { key: 'total_trades', label: '交易次数', pct: false, invert: false },
] as const

const COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4']

function mergeNavSeries(runs: CompareRun[]): Array<Record<string, unknown>> {
  const dateMap = new Map<string, Record<string, unknown>>()
  runs.forEach(r => {
    r.nav_series.forEach(({ date, nav }) => {
      if (!dateMap.has(date)) dateMap.set(date, { date })
      dateMap.get(date)![r.run_id] = nav
    })
  })
  return Array.from(dateMap.values()).sort((a, b) =>
    String(a['date']).localeCompare(String(b['date']))
  )
}

export function ModelCompareTab({ backtestId, selectedModels }: ModelCompareTabProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['backtests', 'compare', backtestId, selectedModels.join(',')],
    queryFn: () => backtestsApi.compare(selectedModels.join(',')),
    enabled: selectedModels.length >= 2,
    staleTime: 60_000,
  })

  if (selectedModels.length < 2) {
    return (
      <div className="text-center py-12 text-gray-400">
        <div className="text-4xl mb-2">📊</div>
        <div className="text-sm">请至少选择 2 个模型进行对比</div>
      </div>
    )
  }

  const runs = data?.runs ?? []
  const navData = mergeNavSeries(runs)

  return (
    <DataState isLoading={isLoading} error={error} isEmpty={runs.length === 0} emptyText="暂无对比数据">
      <div className="space-y-6">
        {/* Metrics comparison table */}
        <div>
          <h3 className="font-semibold text-gray-700 mb-3">关键指标对比</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b bg-gray-50">
                  <th className="py-2 px-3">指标</th>
                  {runs.map(r => (
                    <th key={r.run_id} className="py-2 px-3 text-center min-w-[120px]">
                      <div className="font-semibold text-gray-800 truncate max-w-[120px]" title={r.strategy_id}>
                        {r.strategy_id}
                      </div>
                      <div className="text-xs text-gray-400 font-mono font-normal">{r.run_id.slice(0, 10)}...</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {METRIC_DEFS.map(({ key, label, pct, invert }) => {
                  const vals = runs.map(r => {
                    const v = r.metrics?.[key]
                    return v !== undefined && v !== null ? Number(v) : NaN
                  })
                  const validVals = vals.filter(v => !isNaN(v))
                  const best = validVals.length
                    ? invert ? Math.min(...validVals) : Math.max(...validVals)
                    : NaN
                  return (
                    <tr key={key} className="border-b hover:bg-gray-50">
                      <td className="py-2 px-3 text-gray-600">{label}</td>
                      {vals.map((v, i) => {
                        const isBest = !isNaN(v) && v === best
                        const display = isNaN(v)
                          ? '--'
                          : pct ? `${(v * 100).toFixed(2)}%` : v.toFixed(3)
                        return (
                          <td
                            key={runs[i].run_id}
                            className={`py-2 px-3 text-center font-mono ${
                              isBest ? 'text-green-600 font-bold' : 'text-gray-700'
                            }`}
                          >
                            {display}
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* NAV curve overlay chart */}
        {navData.length > 0 && (
          <div>
            <h3 className="font-semibold text-gray-700 mb-3">净值曲线叠加</h3>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart
                data={navData}
                margin={{ top: 4, right: 16, left: -20, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10 }}
                  interval="preserveStartEnd"
                  tickFormatter={v => String(v).slice(5)}
                />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip formatter={(v: number) => v.toFixed(4)} />
                <Legend />
                {runs.map((r, i) => (
                  <Line
                    key={r.run_id}
                    dataKey={r.run_id}
                    name={r.strategy_id}
                    stroke={COLORS[i % COLORS.length]}
                    dot={false}
                    strokeWidth={2}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </DataState>
  )
}

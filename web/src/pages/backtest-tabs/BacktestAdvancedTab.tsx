import { MetricCard } from '../../components/ui/MetricCard'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { backtestsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import {
  BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
  Cell, ReferenceLine, CartesianGrid,
} from 'recharts'


export function BacktestAdvancedTab() {
  const { id: selectedId } = useParams<{ id: string }>()

  const { data: calendarAnalysisData } = useQuery({
    queryKey: queryKeys.backtests.calendarAnalysis(selectedId!),
    queryFn: () => backtestsApi.getCalendarAnalysis(selectedId!),
    enabled: !!selectedId,
    staleTime: 120_000,
  })

  const { data: tradeAnalysisData } = useQuery({
    queryKey: ['backtests', 'trade-analysis', selectedId!],
    queryFn: () => backtestsApi.getTradeAnalysis(selectedId!),
    enabled: !!selectedId,
    staleTime: 120_000,
  })

  if (!selectedId) return null

  return (
    <div className="space-y-4">
      {/* Calendar Analysis */}
      {calendarAnalysisData ? (
        <>
          {/* Month Effect Heatmap */}
          {calendarAnalysisData.month_effects && (calendarAnalysisData.month_effects as unknown[]).length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">Month Effect</h3>
              <div className="grid grid-cols-6 gap-2">
                {(calendarAnalysisData.month_effects as { month: number; label: string; mean_return: number; win_rate: number; count: number }[]).map(m => {
                  const color = m.mean_return > 0
                    ? `rgba(34, 197, 94, ${Math.min(Math.abs(m.mean_return) * 100, 0.8)})`
                    : m.mean_return < 0
                      ? `rgba(239, 68, 68, ${Math.min(Math.abs(m.mean_return) * 100, 0.8)})`
                      : '#f3f4f6'
                  return (
                    <div key={m.month} className="text-center p-3 rounded-lg" style={{ backgroundColor: color }}>
                      <div className="text-sm font-medium">{m.label}</div>
                      <div className="text-lg font-bold mt-1">{(m.mean_return * 100).toFixed(2)}%</div>
                      <div className="text-xs text-gray-600 mt-0.5">Win {(m.win_rate * 100).toFixed(0)}%</div>
                      <div className="text-xs text-gray-400">{m.count} days</div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Weekday Effect */}
          {calendarAnalysisData.weekday_effects && (calendarAnalysisData.weekday_effects as unknown[]).length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">Weekday Effect</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart
                  data={(calendarAnalysisData.weekday_effects as { weekday: number; label: string; mean_return: number }[]).map(w => ({
                    ...w,
                    mean_return_pct: w.mean_return * 100,
                  }))}
                  margin={{ top: 4, right: 16, left: -20, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${v.toFixed(2)}%`} />
                  <Tooltip formatter={(v: number) => `${v.toFixed(3)}%`} />
                  <ReferenceLine y={0} stroke="#e5e7eb" />
                  <Bar dataKey="mean_return_pct" name="Avg Return" radius={[4, 4, 0, 0]}>
                    {(calendarAnalysisData.weekday_effects as { mean_return: number }[]).map((w, i) => (
                      <Cell key={i} fill={w.mean_return >= 0 ? '#22c55e' : '#ef4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Month-end effect */}
          {calendarAnalysisData.month_end_effect && (
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">Month-End Effect</h3>
              <div className="grid grid-cols-4 gap-4">
                <MetricCard
                  label="Month-End Avg Return"
                  value={`${((calendarAnalysisData.month_end_effect as { month_end_mean: number }).month_end_mean * 100).toFixed(3)}%`}
                  sub={`${(calendarAnalysisData.month_end_effect as { month_end_count: number }).month_end_count} trading days`}
                />
                <MetricCard
                  label="Non-Month-End Avg"
                  value={`${((calendarAnalysisData.month_end_effect as { non_month_end_mean: number }).non_month_end_mean * 100).toFixed(3)}%`}
                  sub={`${(calendarAnalysisData.month_end_effect as { non_month_end_count: number }).non_month_end_count} trading days`}
                />
                <MetricCard
                  label="t-Statistic"
                  value={(calendarAnalysisData.month_end_effect as { t_statistic: number }).t_statistic.toFixed(3)}
                />
                <MetricCard
                  label="p-Value"
                  value={(calendarAnalysisData.month_end_effect as { p_value: number }).p_value.toFixed(4)}
                  warn={(calendarAnalysisData.month_end_effect as { p_value: number }).p_value < 0.05}
                  sub={(calendarAnalysisData.month_end_effect as { p_value: number }).p_value < 0.05 ? 'Statistically significant' : 'Not significant'}
                />
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="card text-center text-gray-400 py-8">
          <div className="text-2xl mb-2">Calendar</div>
          <div>No calendar analysis data</div>
        </div>
      )}

      {/* Trade Analysis */}
      {tradeAnalysisData ? (
        <>
          <div className="card">
            <h3 className="font-semibold text-gray-800 mb-3">Trade Analysis Overview</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <MetricCard
                label="Profit Factor"
                value={Number(tradeAnalysisData.profit_factor ?? 0).toFixed(2)}
                sub="Total profit / Total loss"
              />
              <MetricCard
                label="Payoff Ratio"
                value={Number(tradeAnalysisData.payoff_ratio ?? 0).toFixed(2)}
                sub="Avg win / Avg loss"
              />
              <MetricCard
                label="Expectancy"
                value={Number(tradeAnalysisData.expectancy ?? 0).toFixed(4)}
                sub="Per-trade expected value"
              />
              <MetricCard
                label="Total Trades"
                value={String(tradeAnalysisData.total_trades ?? 0)}
              />
            </div>
          </div>

          {tradeAnalysisData.win_loss_stats && (
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">Win/Loss Statistics</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
                <MetricCard
                  label="Win Rate"
                  value={`${((tradeAnalysisData.win_loss_stats as { win_rate: number }).win_rate * 100).toFixed(1)}%`}
                />
                <MetricCard
                  label="Avg Win"
                  value={`${Number((tradeAnalysisData.win_loss_stats as { avg_win: number }).avg_win).toLocaleString()}`}
                />
                <MetricCard
                  label="Avg Loss"
                  value={`${Number((tradeAnalysisData.win_loss_stats as { avg_loss: number }).avg_loss).toLocaleString()}`}
                  warn
                />
                <MetricCard
                  label="Largest Win"
                  value={`${Number((tradeAnalysisData.win_loss_stats as { largest_win: number }).largest_win).toLocaleString()}`}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-green-50 rounded-lg">
                  <div className="text-sm font-medium text-green-800">Max Win Streak</div>
                  <div className="text-2xl font-bold text-green-700">{(tradeAnalysisData.win_loss_stats as { max_win_streak: number }).max_win_streak} trades</div>
                </div>
                <div className="p-3 bg-red-50 rounded-lg">
                  <div className="text-sm font-medium text-red-800">Max Loss Streak</div>
                  <div className="text-2xl font-bold text-red-700">{(tradeAnalysisData.win_loss_stats as { max_loss_streak: number }).max_loss_streak} trades</div>
                </div>
              </div>
            </div>
          )}

          {tradeAnalysisData.holding_period_stats && (tradeAnalysisData.holding_period_stats as { distribution: unknown[] }).distribution.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">Holding Period Distribution</h3>
              <div className="grid grid-cols-4 gap-4 mb-4">
                <MetricCard label="Mean" value={`${(tradeAnalysisData.holding_period_stats as { mean_days: number }).mean_days} days`} />
                <MetricCard label="Median" value={`${(tradeAnalysisData.holding_period_stats as { median_days: number }).median_days} days`} />
                <MetricCard label="Min" value={`${(tradeAnalysisData.holding_period_stats as { min_days: number }).min_days} days`} />
                <MetricCard label="Max" value={`${(tradeAnalysisData.holding_period_stats as { max_days: number }).max_days} days`} />
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart
                  data={(tradeAnalysisData.holding_period_stats as { distribution: { bucket: string; count: number }[] }).distribution}
                  margin={{ top: 4, right: 16, left: -20, bottom: 0 }}
                >
                  <XAxis dataKey="bucket" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v: number) => `${v} trades`} />
                  <Bar dataKey="count" name="Trades" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      ) : (
        <div className="card text-center text-gray-400 py-8">
          <div className="text-2xl mb-2">Chart</div>
          <div>No trade analysis data</div>
        </div>
      )}
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { backtestsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Legend,
} from 'recharts'

const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const MONTH_POSITION_LABELS: Record<string, string> = {
  early: '月初 (1-5)',
  mid_early: '月中前 (6-15)',
  mid: '月中 (11-20)',
  mid_late: '月中后 (16-25)',
  late: '月末 (26-31)',
}

function fmtPct(v: unknown, digits = 2): string {
  const n = Number(v ?? 0) * 100
  return `${n >= 0 ? '+' : ''}${n.toFixed(digits)}%`
}

function WinRateBadge({ rate }: { rate: number }) {
  const pct = (rate * 100).toFixed(0)
  return (
    <span className={`text-xs font-medium ${rate >= 0.5 ? 'text-green-600' : 'text-red-500'}`}>
      {pct}% win
    </span>
  )
}

export function BacktestCalendarTab() {
  const { id: selectedId } = useParams<{ id: string }>()

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.backtests.calendarAnalysis(selectedId!),
    queryFn: () => backtestsApi.getCalendarAnalysis(selectedId!),
    enabled: !!selectedId,
  })

  if (!selectedId) return null

  if (isLoading) {
    return <div className="text-center text-gray-400 py-12">Loading calendar analysis...</div>
  }

  if (!data) {
    return (
      <div className="card text-center text-gray-400 py-12">
        <div className="text-4xl mb-3">Calendar</div>
        <div className="text-gray-500 mb-2">No calendar analysis data available</div>
        <p className="text-xs text-gray-400">Calendar data is generated automatically after backtest completion</p>
      </div>
    )
  }

  const weekdayData = (data.day_of_week ?? []) as Record<string, unknown>[]
  const monthData = (data.month ?? []) as Record<string, unknown>[]
  const monthPositionData = (data.month_position ?? []) as Record<string, unknown>[]
  const holidayData = (data.holiday ?? []) as Record<string, unknown>[]

  // Build weekday chart data
  const weekdayChartData = weekdayData.map((d, i) => ({
    day: WEEKDAY_LABELS[i] ?? `D${i + 1}`,
    avg_return: Number(d.avg_return ?? 0) * 100,
    win_rate: Number(d.win_rate ?? 0),
    count: Number(d.count ?? 0),
  }))

  // Build month chart data
  const monthChartData = monthData.map((d, i) => ({
    month: MONTH_LABELS[i] ?? `M${i + 1}`,
    avg_return: Number(d.avg_return ?? 0) * 100,
    win_rate: Number(d.win_rate ?? 0),
    count: Number(d.count ?? 0),
  }))

  // Build month position cards
  const monthPositions = monthPositionData.map(d => ({
    label: MONTH_POSITION_LABELS[String(d.position ?? '')] ?? String(d.position ?? ''),
    avg_return: Number(d.avg_return ?? 0),
    win_rate: Number(d.win_rate ?? 0),
    count: Number(d.count ?? 0),
  }))

  // Build holiday effect cards
  const holidayEffects = holidayData.map(d => ({
    label: String(d.label ?? d.period ?? ''),
    avg_return: Number(d.avg_return ?? 0),
    win_rate: Number(d.win_rate ?? 0),
    count: Number(d.count ?? 0),
  }))

  return (
    <div className="space-y-6">
      {/* Day-of-Week Effect */}
      {weekdayChartData.length > 0 && (
        <div className="card p-4">
          <h3 className="font-semibold text-gray-800 mb-1">Day-of-Week Effect</h3>
          <p className="text-xs text-gray-400 mb-4">Average daily return by weekday</p>
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-3 mb-4">
            {weekdayChartData.map((d, i) => (
              <div key={i} className="card text-center py-3">
                <div className={`text-lg font-bold ${Number(d.avg_return) >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                  {fmtPct(Number(d.avg_return) / 100)}
                </div>
                <div className="text-xs text-gray-500 mt-1">{d.day}</div>
                <WinRateBadge rate={d.win_rate} />
                <div className="text-xs text-gray-400 mt-0.5">{d.count} trades</div>
              </div>
            ))}
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={weekdayChartData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${v.toFixed(2)}%`} />
              <Tooltip formatter={(v: number) => `${v.toFixed(3)}%`} />
              <Bar dataKey="avg_return" name="Avg Return" radius={[4, 4, 0, 0]}>
                {weekdayChartData.map((d, i) => (
                  <Cell key={i} fill={d.avg_return >= 0 ? '#22c55e' : '#ef4444'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Month Effect */}
      {monthChartData.length > 0 && (
        <div className="card p-4">
          <h3 className="font-semibold text-gray-800 mb-1">Month Effect</h3>
          <p className="text-xs text-gray-400 mb-4">Average return by calendar month</p>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={monthChartData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${v.toFixed(2)}%`} />
              <Tooltip formatter={(v: number) => `${v.toFixed(3)}%`} />
              <Legend />
              <Bar dataKey="avg_return" name="Avg Return" radius={[4, 4, 0, 0]}>
                {monthChartData.map((d, i) => (
                  <Cell key={i} fill={d.avg_return >= 0 ? '#3b82f6' : '#ef4444'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 mt-4">
            {monthChartData.map((d, i) => (
              <div key={i} className="text-center">
                <div className="text-xs font-medium text-gray-600">{d.month}</div>
                <WinRateBadge rate={d.win_rate} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Month Position Effect */}
      {monthPositions.length > 0 && (
        <div className="card p-4">
          <h3 className="font-semibold text-gray-800 mb-1">Month Position Effect</h3>
          <p className="text-xs text-gray-400 mb-4">Returns at different points within each month</p>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {monthPositions.map((p, i) => (
              <div key={i} className="card text-center py-4">
                <div className={`text-xl font-bold ${p.avg_return >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                  {fmtPct(p.avg_return)}
                </div>
                <div className="text-xs text-gray-500 mt-1">{p.label}</div>
                <WinRateBadge rate={p.win_rate} />
                <div className="text-xs text-gray-400 mt-0.5">{p.count} trades</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Holiday Effect */}
      {holidayEffects.length > 0 && (
        <div className="card p-4">
          <h3 className="font-semibold text-gray-800 mb-1">Holiday Effect</h3>
          <p className="text-xs text-gray-400 mb-4">Returns around market holidays</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {holidayEffects.map((h, i) => (
              <div key={i} className="card text-center py-5">
                <div className={`text-2xl font-bold ${h.avg_return >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                  {fmtPct(h.avg_return)}
                </div>
                <div className="text-sm text-gray-600 mt-2 font-medium">{h.label}</div>
                <WinRateBadge rate={h.win_rate} />
                <div className="text-xs text-gray-400 mt-1">{h.count} trades</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state if all sections are empty */}
      {weekdayChartData.length === 0 && monthChartData.length === 0 &&
       monthPositions.length === 0 && holidayEffects.length === 0 && (
        <div className="card text-center text-gray-400 py-12">
          <div className="text-4xl mb-3">Calendar</div>
          <div className="text-gray-500 mb-2">No calendar effect data found</div>
          <p className="text-xs text-gray-400">This analysis requires completed trade data</p>
        </div>
      )}
    </div>
  )
}

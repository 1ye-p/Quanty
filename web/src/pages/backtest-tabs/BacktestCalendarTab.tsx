import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { MetricCard } from '../../components/ui/MetricCard'
import { useParams } from 'react-router-dom'
import { backtestsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Legend,
} from 'recharts'

function fmtPct(v: unknown, digits = 2): string {
  const n = Number(v ?? 0) * 100
  return `${n >= 0 ? '+' : ''}${n.toFixed(digits)}%`
}

function WinRateBadge({ rate }: { rate: number }) {
  const { t } = useTranslation()
  const pct = (rate * 100).toFixed(0)
  return (
    <span className={`text-xs font-medium ${rate >= 0.5 ? 'text-green-600' : 'text-red-500'}`}>
      {pct}% {t('component.calendar.label.win')}
    </span>
  )
}

export function BacktestCalendarTab() {
  const { t } = useTranslation()
  const { id: selectedId } = useParams<{ id: string }>()

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.backtests.calendarAnalysis(selectedId!),
    queryFn: () => backtestsApi.getCalendarAnalysis(selectedId!),
    enabled: !!selectedId,
  })

  if (!selectedId) return null

  if (isLoading) {
    return <div className="text-center text-gray-400 py-12">{t('component.calendar.empty.loading')}</div>
  }

  if (!data) {
    return (
      <div className="card text-center text-gray-400 py-12">
        <div className="text-4xl mb-3">{t('component.calendar.empty.icon')}</div>
        <div className="text-gray-500 mb-2">{t('component.calendar.empty.no_data')}</div>
        <p className="text-xs text-gray-400">{t('component.calendar.empty.hint')}</p>
      </div>
    )
  }

  const weekdayData = (data.weekday_effects ?? []) as Record<string, unknown>[]
  const monthData = (data.month_effects ?? []) as Record<string, unknown>[]
  const monthEndEffect = data.month_end_effect as Record<string, unknown> | null | undefined
  const holidayEffectsRaw = (data.holiday_effects ?? []) as Record<string, unknown>[]

  // Build weekday chart data (backend: weekday_effects with weekday, label, mean_return, win_rate, count)
  const weekdayChartData = weekdayData.map(d => ({
    day: String(d.label ?? `D${d.weekday}`),
    avg_return: Number(d.mean_return ?? 0), // keep as decimal, fmtPct handles ×100
    win_rate: Number(d.win_rate ?? 0),
    count: Number(d.count ?? 0),
  }))

  // Build month chart data (backend: month_effects with month, label, mean_return, win_rate, count)
  const monthChartData = monthData.map(d => ({
    month: String(d.label ?? `M${d.month}`),
    avg_return: Number(d.mean_return ?? 0), // keep as decimal, fmtPct handles ×100
    win_rate: Number(d.win_rate ?? 0),
    count: Number(d.count ?? 0),
  }))

  // Build month-end effect card (backend: month_end_effect object)
  const monthEndStats = monthEndEffect
    ? {
        month_end_mean: Number(monthEndEffect.month_end_mean ?? 0),
        non_month_end_mean: Number(monthEndEffect.non_month_end_mean ?? 0),
        t_statistic: Number(monthEndEffect.t_statistic ?? 0),
        p_value: Number(monthEndEffect.p_value ?? 0),
        month_end_count: Number(monthEndEffect.month_end_count ?? 0),
      }
    : null

  // Build holiday effect data (backend: holiday_effects with holiday, pre_days)
  interface HolidayPreDay {
    n: number
    mean_return: number
    win_rate: number
    t_stat: number
    count: number
  }
  interface HolidayEffectItem {
    holiday: string
    pre_days: HolidayPreDay[]
  }
  const holidayEffects: HolidayEffectItem[] = holidayEffectsRaw.map(h => ({
    holiday: String(h.holiday ?? ''),
    pre_days: ((h.pre_days ?? []) as Record<string, unknown>[]).map(pd => ({
      n: Number(pd.n ?? 0),
      mean_return: Number(pd.mean_return ?? 0),
      win_rate: Number(pd.win_rate ?? 0),
      t_stat: Number(pd.t_stat ?? 0),
      count: Number(pd.count ?? 0),
    })),
  }))

  // Build aggregated chart data for holiday comparison
  const holidayChartData = holidayEffects.flatMap(h =>
    h.pre_days.map(pd => ({
      holiday: h.holiday,
      label: `${h.holiday}-D${pd.n}`,
      avg_return: pd.mean_return,
      win_rate: pd.win_rate,
      count: pd.count,
    })),
  )

  return (
    <div className="space-y-6">
      {/* Day-of-Week Effect */}
      {weekdayChartData.length > 0 && (
        <div className="card p-4">
          <h3 className="font-semibold text-gray-800 mb-1">{t('component.advanced.section.weekday_effect')}</h3>
          <p className="text-xs text-gray-400 mb-4">{t('component.calendar.hint.day_of_week')}</p>
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-3 mb-4">
            {weekdayChartData.map((d, i) => (
              <div key={i} className="card text-center py-3">
                <div className={`text-lg font-bold ${d.avg_return >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                  {fmtPct(d.avg_return)}
                </div>
                <div className="text-xs text-gray-500 mt-1">{d.day}</div>
                <WinRateBadge rate={d.win_rate} />
                <div className="text-xs text-gray-400 mt-0.5">{t('component.advanced.sub.trades', { count: d.count })}</div>
              </div>
            ))}
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={weekdayChartData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${(v * 100).toFixed(2)}%`} />
              <Tooltip formatter={(v: number) => `${(v * 100).toFixed(3)}%`} />
              <Bar dataKey="avg_return" name={t('component.advanced.series.avg_return')} radius={[4, 4, 0, 0]}>
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
          <h3 className="font-semibold text-gray-800 mb-1">{t('component.advanced.section.month_effect')}</h3>
          <p className="text-xs text-gray-400 mb-4">{t('component.calendar.hint.by_month')}</p>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={monthChartData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${(v * 100).toFixed(2)}%`} />
              <Tooltip formatter={(v: number) => `${(v * 100).toFixed(3)}%`} />
              <Legend />
              <Bar dataKey="avg_return" name={t('component.advanced.series.avg_return')} radius={[4, 4, 0, 0]}>
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

      {/* Month-End Effect */}
      {monthEndStats && (
        <div className="card p-4">
          <h3 className="font-semibold text-gray-800 mb-1">{t('component.advanced.section.month_end_effect')}</h3>
          <p className="text-xs text-gray-400 mb-4">{t('component.calendar.hint.month_end_vs_rest')}</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <MetricCard label={t('component.advanced.label.month_end_avg_return')} value={fmtPct(monthEndStats.month_end_mean)} />
            <MetricCard label={t('component.advanced.label.non_month_end_avg')} value={fmtPct(monthEndStats.non_month_end_mean)} />
            <MetricCard label={t('component.advanced.label.t_statistic')} value={monthEndStats.t_statistic.toFixed(3)} />
            <MetricCard label={t('component.advanced.label.p_value')} value={monthEndStats.p_value.toFixed(4)} />
          </div>
          <p className="text-xs text-gray-400 mt-3">
            {t('component.calendar.hint.month_end_observations', { count: monthEndStats.month_end_count })}
            {monthEndStats.p_value < 0.05
              ? t('component.calendar.hint.significant_95')
              : t('component.calendar.hint.not_significant_95')}
          </p>
        </div>
      )}

      {/* Holiday Effect */}
      {holidayEffects.length > 0 && (
        <div className="card p-4">
          <h3 className="font-semibold text-gray-800 mb-1">{t('component.calendar.section.holiday_effect')}</h3>
          <p className="text-xs text-gray-400 mb-4">
            {t('component.calendar.hint.holiday_effect')}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            {holidayEffects.map((h, hi) => (
              <div key={hi} className="bg-white rounded-xl shadow-sm border p-4">
                <h4 className="font-semibold text-gray-700 mb-3 text-center">{h.holiday}</h4>
                <div className="space-y-2">
                  {h.pre_days.map((pd, pi) => (
                    <div key={pi} className="flex items-center justify-between text-sm">
                      <span className="text-gray-500">{t('component.calendar.label.pre_n_days', { n: pd.n })}</span>
                      <div className="flex items-center gap-3">
                        <span className={pd.mean_return >= 0 ? 'text-green-600 font-medium' : 'text-red-500 font-medium'}>
                          {fmtPct(pd.mean_return)}
                        </span>
                        <WinRateBadge rate={pd.win_rate} />
                        <span className="text-xs text-gray-400">{t('component.advanced.sub.trades', { count: pd.count })}</span>
                      </div>
                    </div>
                  ))}
                </div>
                {/* Show t-stat for D1 as significance indicator */}
                {h.pre_days.length > 0 && h.pre_days[0].count > 0 && (
                  <p className="text-xs text-gray-400 mt-3 text-center">
                    {t('component.calendar.label.t_stat_d1')}: {h.pre_days[0].t_stat.toFixed(2)}
                    {Math.abs(h.pre_days[0].t_stat) >= 1.96
                      ? t('component.calendar.hint.significant_paren')
                      : t('component.calendar.hint.not_significant_paren')}
                  </p>
                )}
              </div>
            ))}
          </div>
          {/* Holiday comparison bar chart */}
          {holidayChartData.length > 0 && (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={holidayChartData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="label" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${(v * 100).toFixed(2)}%`} />
                <Tooltip formatter={(v: number) => `${(v * 100).toFixed(3)}%`} />
                <Bar dataKey="avg_return" name={t('component.advanced.series.avg_return')} radius={[4, 4, 0, 0]}>
                  {holidayChartData.map((d, i) => (
                    <Cell key={i} fill={d.avg_return >= 0 ? '#22c55e' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      )}

      {/* Empty state if all sections are empty */}
      {weekdayChartData.length === 0 && monthChartData.length === 0 && !monthEndStats && holidayEffects.length === 0 && (
        <div className="card text-center text-gray-400 py-12">
          <div className="text-4xl mb-3">{t('component.calendar.empty.icon')}</div>
          <div className="text-gray-500 mb-2">{t('component.calendar.empty.no_effect_data')}</div>
          <p className="text-xs text-gray-400">{t('component.calendar.empty.requires_completed')}</p>
        </div>
      )}
    </div>
  )
}

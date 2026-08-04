import { MetricCard } from '../../components/ui/MetricCard'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { backtestExtApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { PnLChart, type PnLDataPoint } from '@/components/charts/PnLChart'
import { MonthlyReturnHeatmap, type MonthlyReturnRow } from '@/components/charts/MonthlyReturnHeatmap'
import {
  LineChart, Line, Legend,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, AreaChart, Area, ReferenceLine,
} from 'recharts'


export function BacktestTearsheetTab() {
  const { t } = useTranslation()
  const { id: selectedId } = useParams<{ id: string }>()

  const { data: tearsheet } = useQuery({
    queryKey: queryKeys.backtests.tearsheet(selectedId!),
    queryFn: () => backtestExtApi.tearsheet(selectedId!),
    enabled: !!selectedId,
  })

  const snapshots = (tearsheet as Record<string, unknown>)?.snapshots as Record<string, unknown>[] ?? []

  // Compute monthly returns from snapshots
  const monthlyReturns = useMemo((): MonthlyReturnRow[] => {
    if (!snapshots || snapshots.length === 0) return []

    // Group snapshots by year-month
    const monthlyNavs = new Map<string, { startNav: number; endNav: number }>()
    const sortedSnapshots = [...snapshots].sort((a, b) =>
      String(a.trade_date ?? '').localeCompare(String(b.trade_date ?? ''))
    )

    for (const snapshot of sortedSnapshots) {
      const dateStr = String(snapshot.trade_date ?? '').slice(0, 10)
      if (!dateStr) continue

      const yearMonth = dateStr.slice(0, 7) // YYYY-MM
      const nav = Number(snapshot.nav ?? 1)

      if (!monthlyNavs.has(yearMonth)) {
        monthlyNavs.set(yearMonth, { startNav: nav, endNav: nav })
      } else {
        monthlyNavs.get(yearMonth)!.endNav = nav
      }
    }

    // Group by year and compute monthly returns
    const yearMap = new Map<number, (number | null | undefined)[]>()

    for (const [yearMonth, { startNav, endNav }] of monthlyNavs) {
      const year = parseInt(yearMonth.slice(0, 4), 10)
      const month = parseInt(yearMonth.slice(5, 7), 10) - 1 // 0-indexed

      if (!yearMap.has(year)) {
        yearMap.set(year, new Array(12).fill(null))
      }

      const monthlyReturn = startNav > 0 ? (endNav / startNav) - 1 : 0
      yearMap.get(year)![month] = monthlyReturn
    }

    // Convert to MonthlyReturnRow array
    return Array.from(yearMap.entries())
      .map(([year, months]) => ({ year, months }))
      .sort((a, b) => b.year - a.year)
  }, [snapshots])

  // Compute monthly return stats
  const monthlyStats = useMemo(() => {
    if (monthlyReturns.length === 0) return null

    const allReturns: number[] = []
    for (const row of monthlyReturns) {
      for (const ret of row.months) {
        if (ret != null && isFinite(ret)) {
          allReturns.push(ret)
        }
      }
    }

    if (allReturns.length === 0) return null

    const positiveMonths = allReturns.filter(r => r > 0).length
    const winRate = (positiveMonths / allReturns.length) * 100

    const bestReturn = Math.max(...allReturns)
    const worstReturn = Math.min(...allReturns)

    // Find best/worst month labels (break on first match to avoid duplicates)
    let bestMonth = ''
    let worstMonth = ''
    for (const row of monthlyReturns) {
      for (let i = 0; i < row.months.length; i++) {
        if (row.months[i] === bestReturn && !bestMonth) {
          bestMonth = `${row.year}-${String(i + 1).padStart(2, '0')}`
        }
        if (row.months[i] === worstReturn && !worstMonth) {
          worstMonth = `${row.year}-${String(i + 1).padStart(2, '0')}`
        }
      }
    }

    return {
      winRate,
      bestReturn,
      bestMonth,
      worstReturn,
      worstMonth,
      totalMonths: allReturns.length,
    }
  }, [monthlyReturns])

  const pnlData: PnLDataPoint[] = snapshots.length > 0
    ? (() => {
        let peak = 0
        return snapshots.map(s => {
          const nav = Number(s.nav ?? 1)
          peak = Math.max(peak, nav)
          return {
            time: String(s.trade_date ?? '').slice(0, 10),
            nav,
            drawdown: peak > 0 ? (nav - peak) / peak : 0,
          }
        })
      })()
    : []

  const benchmarkNav = ((tearsheet as Record<string, unknown>)?.benchmark_nav ?? []) as { date: string; nav: number }[]
  const benchmarkAssetId = String((tearsheet as Record<string, unknown>)?.benchmark_asset_id ?? '')
  const combinedNav = useMemo(() => {
    if (!snapshots.length) return []
    const bmMap = new Map(benchmarkNav.map(b => [b.date, b.nav]))
    return snapshots.map(s => ({
      date: String(s.trade_date ?? '').slice(0, 10),
      portfolio: Number(s.nav ?? 1),
      benchmark: bmMap.get(String(s.trade_date ?? '').slice(0, 10)) ?? null,
    }))
  }, [snapshots, benchmarkNav])

  if (!selectedId) return null

  return (
    <div className="space-y-4">
      {pnlData.length > 0 ? (
        <div className="card">
          <h3 className="font-semibold text-gray-800 mb-3">{t('component.tearsheet.section.nav_drawdown')}</h3>
          <PnLChart data={pnlData} height={280} showDrawdown />
        </div>
      ) : (
        <div className="card text-center text-gray-400 py-12">
          <div className="text-4xl mb-3">{t('component.tearsheet.empty.chart_icon')}</div>
          <div>{t('component.tearsheet.empty.loading')}</div>
          <div className="text-xs mt-1">{t('component.tearsheet.empty.hint')}</div>
        </div>
      )}

      {/* Monthly Returns Heatmap */}
      {monthlyReturns.length > 0 && (
        <>
          {/* Monthly Stats Cards */}
          {monthlyStats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <MetricCard
                label={t('component.tearsheet.label.monthly_win_rate')}
                value={`${monthlyStats.winRate.toFixed(1)}%`}
                sub={t('component.tearsheet.sub.months_count', { count: monthlyStats.totalMonths })}
              />
              <MetricCard
                label={t('component.tearsheet.label.best_month')}
                value={`${(monthlyStats.bestReturn * 100).toFixed(2)}%`}
                sub={monthlyStats.bestMonth}
              />
              <MetricCard
                label={t('component.tearsheet.label.worst_month')}
                value={`${(monthlyStats.worstReturn * 100).toFixed(2)}%`}
                sub={monthlyStats.worstMonth}
                warn={monthlyStats.worstReturn < 0}
              />
              <MetricCard
                label={t('component.tearsheet.label.positive_months')}
                value={String(Math.round(monthlyStats.totalMonths * monthlyStats.winRate / 100))}
                sub={t('component.tearsheet.sub.of_total', { count: monthlyStats.totalMonths })}
              />
            </div>
          )}
          <MonthlyReturnHeatmap data={monthlyReturns} />
        </>
      )}

      {/* Benchmark overlay chart */}
      {combinedNav.length > 0 && benchmarkNav.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-800">{t('component.tearsheet.section.benchmark_comparison')}</h3>
            {(() => {
              const lastPortfolio = combinedNav[combinedNav.length - 1]?.portfolio ?? 1
              const lastBm = benchmarkNav[benchmarkNav.length - 1]?.nav ?? 1
              const excess = (lastPortfolio / lastBm - 1) * 100
              return (
                <div className="text-sm text-gray-600">
                  {t('component.tearsheet.phrase.excess_return_label')}
                  <span className={`font-mono font-semibold ml-1 ${excess >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                    {excess >= 0 ? '+' : ''}{excess.toFixed(2)}%
                  </span>
                  <span className="text-xs text-gray-400 ml-1">{t('component.tearsheet.phrase.vs_benchmark', { assetId: benchmarkAssetId })}</span>
                </div>
              )
            })()}
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={combinedNav} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd"
                tickFormatter={v => String(v).slice(5)} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => v.toFixed(2)} />
              <Tooltip formatter={(v: number) => v.toFixed(4)} />
              <Legend />
              <Line dataKey="portfolio" name={t('component.tearsheet.series.strategy')} stroke="#3b82f6" dot={false} strokeWidth={2} />
              <Line dataKey="benchmark" name={benchmarkAssetId || t('component.tearsheet.series.benchmark')} stroke="#94a3b8"
                strokeDasharray="5 3" dot={false} strokeWidth={1.5} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Excess Return Cumulative Curve */}
      {combinedNav.length > 0 && benchmarkNav.length > 0 && (() => {
        const excessData = combinedNav
          .filter(d => d.benchmark !== null && d.benchmark > 0)
          .map(d => ({
            date: d.date,
            excess: ((d.portfolio as number) / (d.benchmark as number) - 1) * 100,
          }))
        if (excessData.length === 0) return null
        return (
          <div className="card">
            <h3 className="font-semibold text-gray-800 mb-3">{t('component.tearsheet.section.cumulative_excess')}</h3>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={excessData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd"
                  tickFormatter={v => String(v).slice(5)} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${v.toFixed(1)}%`} />
                <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
                <ReferenceLine y={0} stroke="#e5e7eb" />
                <Area type="monotone" dataKey="excess" name={t('component.tearsheet.series.excess_return')} stroke="#10b981" fill="#d1fae5" fillOpacity={0.6} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )
      })()}

      {/* Rolling TE & IR */}
      {combinedNav.length > 0 && benchmarkNav.length > 0 && (() => {
        const validData = combinedNav.filter(d => d.benchmark !== null && d.benchmark > 0)
        if (validData.length < 21) return null

        const window = 20
        const rollingData: { date: string; te: number; ir: number }[] = []
        for (let i = window; i < validData.length; i++) {
          const windowSlice = validData.slice(i - window, i)
          const excessRets = windowSlice.map(d =>
            (d.portfolio as number) / (d.benchmark as number) - 1
          )
          const mean = excessRets.reduce((a, b) => a + b, 0) / excessRets.length
          const variance = excessRets.reduce((a, b) => a + (b - mean) ** 2, 0) / (excessRets.length - 1)
          const te = Math.sqrt(variance) * Math.sqrt(252)
          const ir = te > 0 ? (mean * 252) / te : 0
          rollingData.push({ date: validData[i].date, te: te * 100, ir })
        }

        if (rollingData.length === 0) return null
        return (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">{t('component.tearsheet.section.rolling_te')}</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={rollingData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd"
                    tickFormatter={v => String(v).slice(5)} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${v.toFixed(1)}%`} />
                  <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
                  <Line type="monotone" dataKey="te" name={t('component.tearsheet.series.te')} stroke="#f59e0b" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">{t('component.tearsheet.section.rolling_ir')}</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={rollingData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd"
                    tickFormatter={v => String(v).slice(5)} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v: number) => v.toFixed(3)} />
                  <ReferenceLine y={0} stroke="#e5e7eb" />
                  <Line type="monotone" dataKey="ir" name={t('component.tearsheet.series.ir')} stroke="#8b5cf6" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )
      })()}

      {/* Up/Down Capture Ratio */}
      {combinedNav.length > 0 && benchmarkNav.length > 0 && (() => {
        const validData = combinedNav.filter(d => d.benchmark !== null && d.benchmark > 1)
        if (validData.length < 2) return null

        let upPort = 0, upBm = 0, upCount = 0
        let downPort = 0, downBm = 0, downCount = 0
        for (let i = 1; i < validData.length; i++) {
          const bmRet = (validData[i].benchmark as number) / (validData[i - 1].benchmark as number) - 1
          const portRet = (validData[i].portfolio as number) / (validData[i - 1].portfolio as number) - 1
          if (bmRet > 0) {
            upPort += portRet
            upBm += bmRet
            upCount++
          } else if (bmRet < 0) {
            downPort += portRet
            downBm += bmRet
            downCount++
          }
        }

        const upCapture = upCount > 0 && upBm > 0 ? (upPort / upBm) * 100 : 0
        const downCapture = downCount > 0 && downBm < 0 ? (downPort / downBm) * 100 : 0

        return (
          <div className="card">
            <h3 className="font-semibold text-gray-800 mb-3">{t('component.tearsheet.section.capture_ratio')}</h3>
            <div className="grid grid-cols-4 gap-4">
              <MetricCard label={t('component.tearsheet.label.up_capture')} value={`${upCapture.toFixed(1)}%`} sub={t('component.tearsheet.sub.up_days', { count: upCount })} />
              <MetricCard label={t('component.tearsheet.label.down_capture')} value={`${downCapture.toFixed(1)}%`} sub={t('component.tearsheet.sub.down_days', { count: downCount })} warn={downCapture > 100} />
              <MetricCard label={t('component.tearsheet.label.up_participation')} value={String(upCount)} sub={t('component.tearsheet.sub.up_when_up')} />
              <MetricCard label={t('component.tearsheet.label.down_participation')} value={String(downCount)} sub={t('component.tearsheet.sub.down_when_down')} />
            </div>
          </div>
        )
      })()}

      {tearsheet && (
        <div className="card">
          <h3 className="font-semibold text-gray-800 mb-3">{t('component.tearsheet.section.raw_data')}</h3>
          <pre className="text-xs text-gray-500 overflow-x-auto bg-gray-50 rounded-lg p-3">
            {JSON.stringify(tearsheet, null, 2).slice(0, 1000)}...
          </pre>
        </div>
      )}
    </div>
  )
}

/**
 * BenchmarkCompare — Strategy vs Benchmark comparison chart with relative metrics.
 *
 * Shows:
 *  1. NAV overlay (strategy + benchmark lines)
 *  2. Cumulative excess return area chart
 *  3. Relative metrics cards (Alpha, Beta, Tracking Error, Information Ratio)
 *
 * Handles missing benchmark data gracefully.
 */
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  LineChart, Line, AreaChart, Area,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend, ReferenceLine,
} from 'recharts'
import { MetricCard } from '../ui/MetricCard'
import { ROLLING_WINDOWS } from '@/lib/constants'
import { RollingMetricsChart } from './RollingMetricsChart'

export interface NavPoint {
  date: string
  nav: number
}

interface Props {
  /** Strategy NAV series [{date, nav}] */
  strategyNav: NavPoint[]
  /** Benchmark NAV series [{date, nav}] (optional) */
  benchmarkNav?: NavPoint[]
  /** Benchmark label for display */
  benchmarkLabel?: string
  /** Rebalance dates to show as vertical markers (optional) */
  rebalanceDates?: string[]
}

/** Annualization factor for daily returns (252 trading days). */
const ANN_FACTOR = 252

/**
 * Merge strategy and benchmark onto the same date timeline.
 * Strategy dates are the primary axis; benchmark values are looked up by date.
 */
function mergeTimelines(
  strategy: NavPoint[],
  benchmark: NavPoint[],
): { date: string; strategy: number; benchmark: number }[] {
  const bmMap = new Map(benchmark.map(b => [b.date, b.nav]))
  return strategy
    .map(s => ({
      date: s.date,
      strategy: s.nav,
      benchmark: bmMap.get(s.date) ?? NaN,
    }))
    .filter(d => isFinite(d.benchmark))
}

/** Compute relative metrics from merged daily NAV data. Returns null if insufficient data. */
function computeRelativeMetrics(
  merged: { date: string; strategy: number; benchmark: number }[],
): {
  alpha: number; beta: number; trackingError: number; informationRatio: number
  upCapture: number; downCapture: number; captureRatio: number
  correlation: number; rSquared: number
} | null {
  if (merged.length < 2) return null

  // Daily returns
  const stratReturns: number[] = []
  const bmReturns: number[] = []
  for (let i = 1; i < merged.length; i++) {
    const sRet = merged[i].strategy / merged[i - 1].strategy - 1
    const bRet = merged[i].benchmark / merged[i - 1].benchmark - 1
    stratReturns.push(sRet)
    bmReturns.push(bRet)
  }

  const n = stratReturns.length
  if (n < 2) return null

  // Means
  const meanS = stratReturns.reduce((a, b) => a + b, 0) / n
  const meanB = bmReturns.reduce((a, b) => a + b, 0) / n

  // Covariance and variance of benchmark
  let cov = 0
  let varB = 0
  let varS = 0
  for (let i = 0; i < n; i++) {
    const ds = stratReturns[i] - meanS
    const db = bmReturns[i] - meanB
    cov += ds * db
    varB += db * db
    varS += ds * ds
  }
  cov /= n - 1
  varB /= n - 1
  varS /= n - 1

  // Beta = Cov(Rs, Rb) / Var(Rb)
  const beta = varB > 0 ? cov / varB : 0

  // Alpha (annualized Jensen's alpha): alpha = (meanS - beta * meanB) * 252
  const alpha = (meanS - beta * meanB) * ANN_FACTOR

  // Tracking error: annualized std of excess returns
  const excessReturns = stratReturns.map((r, i) => r - bmReturns[i])
  const meanExcess = excessReturns.reduce((a, b) => a + b, 0) / n
  const varExcess = excessReturns.reduce((a, b) => a + (b - meanExcess) ** 2, 0) / (n - 1)
  const trackingError = Math.sqrt(varExcess) * Math.sqrt(ANN_FACTOR)

  // Information ratio: annualized mean excess / tracking error
  const informationRatio = trackingError > 0
    ? (meanExcess * ANN_FACTOR) / trackingError
    : 0

  // Capture ratios
  let upStratSum = 0, upBmSum = 0, upCount = 0
  let downStratSum = 0, downBmSum = 0, downCount = 0
  for (let i = 0; i < n; i++) {
    if (bmReturns[i] > 0) {
      upStratSum += stratReturns[i]
      upBmSum += bmReturns[i]
      upCount++
    } else if (bmReturns[i] < 0) {
      downStratSum += stratReturns[i]
      downBmSum += bmReturns[i]
      downCount++
    }
  }
  const upCapture = upCount > 0 && upBmSum !== 0 ? (upStratSum / upCount) / (upBmSum / upCount) : 1
  const downCapture = downCount > 0 && downBmSum !== 0 ? (downStratSum / downCount) / (downBmSum / downCount) : 1
  const captureRatio = downCapture !== 0 ? upCapture / downCapture : 1

  // Correlation and R²
  const stdDevS = Math.sqrt(varS)
  const stdDevB = Math.sqrt(varB)
  const correlation = (stdDevS > 0 && stdDevB > 0) ? cov / (stdDevS * stdDevB) : 0
  const rSquared = correlation * correlation

  return {
    alpha, beta, trackingError, informationRatio,
    upCapture, downCapture, captureRatio,
    correlation, rSquared,
  }
}

export function BenchmarkCompare({
  strategyNav,
  benchmarkNav,
  benchmarkLabel = 'Benchmark',
  rebalanceDates,
}: Props) {
  const { t } = useTranslation()
  // Merge data
  const merged = useMemo(() => {
    if (!benchmarkNav || benchmarkNav.length === 0 || strategyNav.length === 0) return []
    return mergeTimelines(strategyNav, benchmarkNav)
  }, [strategyNav, benchmarkNav])

  // Compute excess return series
  const excessData = useMemo(() => {
    if (merged.length === 0) return []
    return merged.map(d => ({
      date: d.date,
      excess: ((d.strategy / d.benchmark) - 1) * 100,
    }))
  }, [merged])

  // Compute relative metrics
  const metrics = useMemo(() => computeRelativeMetrics(merged), [merged])

  // Rolling Beta/Alpha
  const [benchmarkRollingWindow, setBenchmarkRollingWindow] = useState(60)

  const rollingBetaAlphaData = useMemo(() => {
    if (merged.length < 2) return []

    // Compute daily returns
    const stratReturns: number[] = []
    const bmReturns: number[] = []
    const dates: string[] = []
    for (let i = 1; i < merged.length; i++) {
      stratReturns.push(merged[i].strategy / merged[i - 1].strategy - 1)
      bmReturns.push(merged[i].benchmark / merged[i - 1].benchmark - 1)
      dates.push(merged[i].date)
    }

    if (stratReturns.length < benchmarkRollingWindow) return []

    const result: { date: string; values: Record<string, number> }[] = []
    for (let i = benchmarkRollingWindow - 1; i < stratReturns.length; i++) {
      const sSlice = stratReturns.slice(i - benchmarkRollingWindow + 1, i + 1)
      const bSlice = bmReturns.slice(i - benchmarkRollingWindow + 1, i + 1)
      const n = sSlice.length

      const meanS = sSlice.reduce((a, b) => a + b, 0) / n
      const meanB = bSlice.reduce((a, b) => a + b, 0) / n

      let cov = 0
      let varB = 0
      for (let j = 0; j < n; j++) {
        const ds = sSlice[j] - meanS
        const db = bSlice[j] - meanB
        cov += ds * db
        varB += db * db
      }
      cov /= n - 1
      varB /= n - 1

      const beta = varB > 0 ? cov / varB : 0
      const alpha = (meanS - beta * meanB) * ANN_FACTOR

      result.push({
        date: dates[i],
        values: { beta, alpha },
      })
    }
    return result
  }, [merged, benchmarkRollingWindow])

  // Filter rebalance dates to those within the merged data range
  const visibleRebalanceDates = useMemo(() => {
    if (!rebalanceDates || rebalanceDates.length === 0 || merged.length === 0) return []
    const dateSet = new Set(merged.map(d => d.date))
    return rebalanceDates.filter(d => dateSet.has(d))
  }, [rebalanceDates, merged])

  // Early return if no benchmark data
  if (!benchmarkNav || benchmarkNav.length === 0) {
    return null
  }

  if (merged.length === 0) {
    return (
      <div className="card text-center text-gray-400 py-8">
        <div className="text-3xl mb-2">{t('component.charts.benchmark_compare.empty_title')}</div>
        <div className="text-sm">{t('component.charts.benchmark_compare.no_overlap')}</div>
      </div>
    )
  }

  // Final excess return for header
  const lastExcess = excessData.length > 0 ? excessData[excessData.length - 1].excess : 0

  return (
    <div className="space-y-4">
      {/* NAV Overlay */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-gray-800">{t('component.charts.benchmark_compare.title')}</h3>
          <div className="text-sm text-gray-600">
            {t('component.charts.benchmark_compare.excess_return')}:
            <span className={`font-mono font-semibold ml-1 ${lastExcess >= 0 ? 'text-green-600' : 'text-red-500'}`}>
              {lastExcess >= 0 ? '+' : ''}{lastExcess.toFixed(2)}%
            </span>
            <span className="text-xs text-gray-400 ml-1">{t('component.charts.benchmark_compare.vs_benchmark', { benchmark: benchmarkLabel })}</span>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={merged} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10 }}
              interval="preserveStartEnd"
              tickFormatter={v => String(v).slice(5)}
            />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={v => v.toFixed(2)} />
            <Tooltip formatter={(v: number) => v.toFixed(4)} />
            <Legend />
            {visibleRebalanceDates.length > 0 && visibleRebalanceDates.length <= 60 && (
              <>
                <ReferenceLine
                  x={visibleRebalanceDates[0]}
                  stroke="#f59e0b"
                  strokeDasharray="4 4"
                  strokeWidth={1}
                  label={{ value: t('component.charts.benchmark_compare.rebalance'), position: 'top', fontSize: 9, fill: '#f59e0b' }}
                />
                {visibleRebalanceDates.slice(1).map(d => (
                  <ReferenceLine
                    key={d}
                    x={d}
                    stroke="#f59e0b"
                    strokeDasharray="4 4"
                    strokeWidth={1}
                  />
                ))}
              </>
            )}
            <Line
              dataKey="strategy"
              name={t('component.charts.benchmark_compare.line_strategy')}
              stroke="#3b82f6"
              dot={false}
              strokeWidth={2}
            />
            <Line
              dataKey="benchmark"
              name={benchmarkLabel}
              stroke="#94a3b8"
              strokeDasharray="5 3"
              dot={false}
              strokeWidth={1.5}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Cumulative Excess Return */}
      {excessData.length > 0 && (
        <div className="card">
          <h3 className="font-semibold text-gray-800 mb-3">{t('component.charts.benchmark_compare.cumulative_excess')}</h3>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={excessData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10 }}
                interval="preserveStartEnd"
                tickFormatter={v => String(v).slice(5)}
              />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${v.toFixed(1)}%`} />
              <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
              <ReferenceLine y={0} stroke="#e5e7eb" />
              <Area
                type="monotone"
                dataKey="excess"
                name={t('component.charts.benchmark_compare.area_excess')}
                stroke="#10b981"
                fill="#d1fae5"
                fillOpacity={0.6}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Relative Metrics Cards */}
      {metrics && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <MetricCard
              label={t('component.charts.benchmark_compare.metric_alpha')}
              value={`${(metrics.alpha * 100).toFixed(2)}%`}
              sub={t('component.charts.benchmark_compare.card_alpha_sub')}
              warn={metrics.alpha < 0}
            />
            <MetricCard
              label={t('component.charts.benchmark_compare.metric_beta')}
              value={metrics.beta.toFixed(3)}
              sub={t('component.charts.benchmark_compare.card_beta_sub')}
            />
            <MetricCard
              label={t('component.charts.benchmark_compare.metric_tracking_error')}
              value={`${(metrics.trackingError * 100).toFixed(2)}%`}
              sub={t('component.charts.benchmark_compare.card_te_sub')}
            />
            <MetricCard
              label={t('component.charts.benchmark_compare.metric_information_ratio')}
              value={metrics.informationRatio.toFixed(3)}
              sub={t('component.charts.benchmark_compare.card_ir_sub')}
              warn={metrics.informationRatio < 0}
            />
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
            <MetricCard
              label={t('component.charts.benchmark_compare.metric_up_capture')}
              value={`${(metrics.upCapture * 100).toFixed(1)}%`}
              sub={t('component.charts.benchmark_compare.card_up_capture_sub')}
              good={metrics.upCapture > 1}
              warn={metrics.upCapture < 1}
            />
            <MetricCard
              label={t('component.charts.benchmark_compare.metric_down_capture')}
              value={`${(metrics.downCapture * 100).toFixed(1)}%`}
              sub={t('component.charts.benchmark_compare.card_down_capture_sub')}
              good={metrics.downCapture < 1}
              warn={metrics.downCapture > 1}
            />
            <MetricCard
              label={t('component.charts.benchmark_compare.metric_capture_ratio')}
              value={metrics.captureRatio.toFixed(3)}
              sub={t('component.charts.benchmark_compare.card_capture_ratio_sub')}
              good={metrics.captureRatio > 1}
              warn={metrics.captureRatio < 1}
            />
            <MetricCard
              label={t('component.charts.benchmark_compare.metric_correlation')}
              value={metrics.correlation.toFixed(4)}
              sub={t('component.charts.benchmark_compare.card_correlation_sub')}
            />
            <MetricCard
              label={t('component.charts.benchmark_compare.metric_r_squared')}
              value={metrics.rSquared.toFixed(4)}
              sub={t('component.charts.benchmark_compare.card_r_squared_sub')}
            />
          </div>
        </>
      )}

      {/* Rolling Beta / Alpha */}
      {rollingBetaAlphaData.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-end">
            <label className="text-xs text-gray-500 mr-2">{t('component.charts.benchmark_compare.rolling_window')}</label>
            <select
              value={benchmarkRollingWindow}
              onChange={e => setBenchmarkRollingWindow(Number(e.target.value))}
              className="text-xs border border-gray-200 rounded px-2 py-1 bg-white text-gray-700 focus:outline-none focus:ring-1 focus:ring-brand-400"
            >
              {ROLLING_WINDOWS.map(w => <option key={w} value={w}>{w}d</option>)}
            </select>
          </div>
          <RollingMetricsChart
            data={rollingBetaAlphaData}
            metrics={[
              { key: 'beta', label: t('component.charts.benchmark_compare.rolling_beta'), color: '#8b5cf6' },
              { key: 'alpha', label: t('component.charts.benchmark_compare.rolling_alpha'), color: '#10b981' },
            ]}
            window={benchmarkRollingWindow}
            title={t('component.charts.benchmark_compare.rolling_beta_alpha_title')}
            referenceLines={[
              { value: 1, label: t('component.charts.benchmark_compare.ref_beta_one'), color: '#c084fc' },
              { value: 0, label: t('component.charts.benchmark_compare.ref_zero'), color: '#e5e7eb' },
            ]}
          />
        </div>
      )}
    </div>
  )
}

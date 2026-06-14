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
import { useMemo } from 'react'
import {
  LineChart, Line, AreaChart, Area,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend, ReferenceLine,
} from 'recharts'
import { MetricCard } from '../ui/MetricCard'

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

/**
 * Compute relative metrics from merged daily NAV data.
 * Returns null if insufficient data.
 */
function computeRelativeMetrics(
  merged: { date: string; strategy: number; benchmark: number }[],
): { alpha: number; beta: number; trackingError: number; informationRatio: number } | null {
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
  for (let i = 0; i < n; i++) {
    const ds = stratReturns[i] - meanS
    const db = bmReturns[i] - meanB
    cov += ds * db
    varB += db * db
  }
  cov /= n - 1
  varB /= n - 1

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

  return { alpha, beta, trackingError, informationRatio }
}

export function BenchmarkCompare({
  strategyNav,
  benchmarkNav,
  benchmarkLabel = 'Benchmark',
}: Props) {
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

  // Early return if no benchmark data
  if (!benchmarkNav || benchmarkNav.length === 0) {
    return null
  }

  if (merged.length === 0) {
    return (
      <div className="card text-center text-gray-400 py-8">
        <div className="text-3xl mb-2">Chart</div>
        <div className="text-sm">No overlapping dates between strategy and benchmark</div>
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
          <h3 className="font-semibold text-gray-800">Benchmark Comparison</h3>
          <div className="text-sm text-gray-600">
            Excess Return:
            <span className={`font-mono font-semibold ml-1 ${lastExcess >= 0 ? 'text-green-600' : 'text-red-500'}`}>
              {lastExcess >= 0 ? '+' : ''}{lastExcess.toFixed(2)}%
            </span>
            <span className="text-xs text-gray-400 ml-1">vs {benchmarkLabel}</span>
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
            <Line
              dataKey="strategy"
              name="Strategy"
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
          <h3 className="font-semibold text-gray-800 mb-3">Cumulative Excess Return</h3>
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
                name="Excess Return"
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
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <MetricCard
            label="Alpha"
            value={`${(metrics.alpha * 100).toFixed(2)}%`}
            sub="Annualized Jensen's α"
            warn={metrics.alpha < 0}
          />
          <MetricCard
            label="Beta"
            value={metrics.beta.toFixed(3)}
            sub="Systematic risk exposure"
          />
          <MetricCard
            label="Tracking Error"
            value={`${(metrics.trackingError * 100).toFixed(2)}%`}
            sub="Annualized TE"
          />
          <MetricCard
            label="Information Ratio"
            value={metrics.informationRatio.toFixed(3)}
            sub="Excess return / TE"
            warn={metrics.informationRatio < 0}
          />
        </div>
      )}
    </div>
  )
}

import { MetricCard } from '../../components/ui/MetricCard'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { backtestsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import type { RoundTrip } from '@/lib/types'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  ScatterChart, Scatter, ZAxis, ReferenceLine,
} from 'recharts'

const PROFIT_COLOR = '#10b981'
const LOSS_COLOR = '#ef4444'

function fmt(n: unknown, digits = 2): string {
  return Number(n ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

/** Compute long/short split stats from round-trips */
function computeLongShortStats(roundTrips: RoundTrip[]) {
  const groups = { long: [] as RoundTrip[], short: [] as RoundTrip[] }
  for (const rt of roundTrips) {
    if (rt.direction === 'long' || rt.direction === 'short') {
      groups[rt.direction].push(rt)
    }
  }

  const calcStats = (trades: RoundTrip[]) => {
    if (trades.length === 0) return null
    const wins = trades.filter(t => t.pnl > 0)
    const losses = trades.filter(t => t.pnl <= 0)
    const totalPnl = trades.reduce((s, t) => s + t.pnl, 0)
    const avgHolding = trades.reduce((s, t) => s + (t.holding_days ?? 0), 0) / trades.length
    const avgWin = wins.length > 0 ? wins.reduce((s, t) => s + t.pnl, 0) / wins.length : 0
    const avgLoss = losses.length > 0 ? losses.reduce((s, t) => s + t.pnl, 0) / losses.length : 0
    const winRate = wins.length / trades.length
    const expectancy = winRate * avgWin + (1 - winRate) * avgLoss
    return {
      totalTrades: trades.length,
      winRate,
      avgHolding,
      avgWin,
      avgLoss,
      expectancy,
      totalPnl,
    }
  }

  return {
    long: calcStats(groups.long),
    short: calcStats(groups.short),
  }
}

/** Custom tooltip for MFE/MAE scatter */
function MfeMaeTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: RoundTrip & { isProfit: boolean } }> }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-white rounded-lg shadow-lg border p-3 text-xs max-w-[240px]">
      <div className="font-semibold text-gray-800 mb-1">{d.asset_id}</div>
      <div className="text-gray-500 mb-2">
        {d.entry_date} &rarr; {d.exit_date} ({d.holding_days ?? '?'}d)
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1">
        <span className="text-gray-500">Direction</span>
        <span className={d.direction === 'long' ? 'text-blue-600' : 'text-purple-600'}>{d.direction}</span>
        <span className="text-gray-500">P&L</span>
        <span className={d.pnl >= 0 ? 'text-green-600' : 'text-red-600'}>{fmt(d.pnl)}</span>
        <span className="text-gray-500">Return</span>
        <span>{(d.return_pct * 100).toFixed(2)}%</span>
        <span className="text-gray-500">MFE</span>
        <span className="text-green-600">{fmt(d.mfe)}</span>
        <span className="text-gray-500">MAE</span>
        <span className="text-red-600">{fmt(d.mae)}</span>
      </div>
    </div>
  )
}

export function BacktestTradeAnalysisTab() {
  const { id } = useParams<{ id: string }>()

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.backtests.tradeAnalysis(id!),
    queryFn: () => backtestsApi.getTradeAnalysis(id!),
    enabled: !!id,
    staleTime: 120_000,
  })

  const { data: roundTripData } = useQuery({
    queryKey: queryKeys.backtests.roundTrips(id!),
    queryFn: () => backtestsApi.getRoundTrips(id!),
    enabled: !!id,
    staleTime: 120_000,
  })

  if (!id) return null

  if (isLoading) {
    return <div className="text-center text-gray-400 py-12">Loading trade analysis...</div>
  }

  if (!data) {
    return <div className="text-center text-gray-400 py-12">No trade data available for analysis</div>
  }

  // Core metrics
  const totalTrades = Number(data.total_trades ?? 0)
  const winRate = Number(data.win_rate ?? 0)
  const profitFactor = Number(data.profit_factor ?? 0)
  const avgHoldingDays = Number(data.avg_holding_days ?? 0)
  const avgWin = Number(data.avg_win ?? 0)
  const avgLoss = Number(data.avg_loss ?? 0)
  const expectancy = Number(data.expectancy ?? 0)
  const totalPnl = Number(data.total_pnl ?? 0)

  // Win/Loss streaks
  const maxWinStreak = Number(data.max_win_streak ?? 0)
  const maxLossStreak = Number(data.max_loss_streak ?? 0)
  const avgWinStreak = Number(data.avg_win_streak ?? 0)
  const avgLossStreak = Number(data.avg_loss_streak ?? 0)

  // PnL distribution histogram
  const pnlDistribution = (data.pnl_distribution ?? []) as { range: string; count: number; label?: string }[]
  const pnlHistData = pnlDistribution.map(d => ({
    label: d.label ?? d.range,
    count: d.count,
    isProfit: (d.label ?? d.range).startsWith('-') === false && Number((d.label ?? d.range).replace(/[^0-9.\-]/g, '')) >= 0,
  }))

  // Holding time distribution
  const holdingDistribution = (data.holding_time_distribution ?? []) as { range: string; count: number; label?: string }[]
  const holdingHistData = holdingDistribution.map(d => ({
    label: d.label ?? d.range,
    count: d.count,
  }))

  // By-asset PnL (top 20)
  const assetPnlRaw = (data.asset_pnl ?? data.by_asset_pnl ?? []) as { asset: string; pnl: number }[]
  const assetPnlData = assetPnlRaw
    .sort((a, b) => b.pnl - a.pnl)
    .slice(0, 20)
    .map(d => ({
      asset: d.asset.length > 10 ? d.asset.slice(0, 10) : d.asset,
      pnl: +d.pnl.toFixed(2),
    }))

  // MFE/MAE scatter data
  const roundTrips = roundTripData?.round_trips ?? []
  const scatterData = roundTrips.map(rt => ({
    ...rt,
    isProfit: rt.pnl > 0,
  }))
  const profitScatter = scatterData.filter(d => d.isProfit)
  const lossScatter = scatterData.filter(d => !d.isProfit)

  // Long/Short split
  const lsStats = roundTrips.length > 0 ? computeLongShortStats(roundTrips) : null

  // For the diagonal reference line, find the max extent
  const maxExtent = scatterData.length > 0
    ? Math.max(
        ...scatterData.map(d => Math.max(Math.abs(d.mfe), Math.abs(d.mae))),
        1,
      )
    : 1

  return (
    <div className="space-y-6">
      {/* Core metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard label="Total Trades" value={String(totalTrades)} />
        <MetricCard label="Win Rate" value={`${(winRate * 100).toFixed(1)}%`} />
        <MetricCard label="Profit Factor" value={fmt(profitFactor)} />
        <MetricCard label="Avg Holding Days" value={fmt(avgHoldingDays, 1)} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard label="Total P&L" value={fmt(totalPnl)} warn={totalPnl < 0} />
        <MetricCard label="Avg Win" value={fmt(avgWin)} />
        <MetricCard label="Avg Loss" value={fmt(avgLoss)} warn={avgLoss < 0} />
        <MetricCard label="Expectancy" value={fmt(expectancy)} />
      </div>

      {/* Win/Loss streaks */}
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <h3 className="font-semibold text-gray-800 mb-3">Win/Loss Streaks</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">{maxWinStreak}</div>
            <div className="text-xs text-gray-500 mt-1">Max Win Streak</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-red-600">{maxLossStreak}</div>
            <div className="text-xs text-gray-500 mt-1">Max Loss Streak</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-500">{fmt(avgWinStreak, 1)}</div>
            <div className="text-xs text-gray-500 mt-1">Avg Win Streak</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-red-500">{fmt(avgLossStreak, 1)}</div>
            <div className="text-xs text-gray-500 mt-1">Avg Loss Streak</div>
          </div>
        </div>
      </div>

      {/* MFE/MAE Scatter Plot */}
      {scatterData.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border p-4">
          <h3 className="font-semibold text-gray-800 mb-1">MFE / MAE Scatter</h3>
          <p className="text-xs text-gray-500 mb-3">
            Maximum Favorable Excursion vs Maximum Adverse Excursion per trade. Each dot is one round-trip.
          </p>
          <ResponsiveContainer width="100%" height={360}>
            <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                type="number"
                dataKey="mae"
                name="MAE"
                tick={{ fontSize: 10 }}
                label={{ value: 'MAE (Adverse)', position: 'insideBottom', offset: -4, fontSize: 11, fill: '#6b7280' }}
              />
              <YAxis
                type="number"
                dataKey="mfe"
                name="MFE"
                tick={{ fontSize: 10 }}
                label={{ value: 'MFE (Favorable)', angle: -90, position: 'insideLeft', offset: 10, fontSize: 11, fill: '#6b7280' }}
              />
              <ZAxis range={[40, 40]} />
              <Tooltip content={<MfeMaeTooltip />} />
              <ReferenceLine
                segment={[{ x: 0, y: 0 }, { x: maxExtent, y: maxExtent }]}
                stroke="#94a3b8"
                strokeDasharray="6 4"
                strokeWidth={1}
              />
              <Scatter name="Profit" data={profitScatter} fill={PROFIT_COLOR} fillOpacity={0.7} />
              <Scatter name="Loss" data={lossScatter} fill={LOSS_COLOR} fillOpacity={0.7} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Long/Short Split Analysis */}
      {lsStats && (lsStats.long || lsStats.short) && (
        <div className="bg-white rounded-xl shadow-sm border p-4">
          <h3 className="font-semibold text-gray-800 mb-3">Long vs Short Analysis</h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Grouped bar chart */}
            <LongShortBarChart stats={lsStats} />
            {/* Side-by-side metric cards */}
            <div className="grid grid-cols-2 gap-3">
              {lsStats.long && (
                <div className="space-y-2">
                  <div className="text-sm font-medium text-blue-600 flex items-center gap-1">
                    <span className="inline-block w-3 h-3 rounded-sm bg-blue-500" />
                    Long
                  </div>
                  <div className="space-y-1.5 text-xs">
                    <LsMetric label="Trades" value={String(lsStats.long.totalTrades)} />
                    <LsMetric label="Win Rate" value={`${(lsStats.long.winRate * 100).toFixed(1)}%`} color={lsStats.long.winRate >= 0.5 ? 'green' : 'red'} />
                    <LsMetric label="Avg Hold" value={`${fmt(lsStats.long.avgHolding, 1)}d`} />
                    <LsMetric label="Expectancy" value={fmt(lsStats.long.expectancy)} color={lsStats.long.expectancy >= 0 ? 'green' : 'red'} />
                    <LsMetric label="Total P&L" value={fmt(lsStats.long.totalPnl)} color={lsStats.long.totalPnl >= 0 ? 'green' : 'red'} />
                  </div>
                </div>
              )}
              {lsStats.short && (
                <div className="space-y-2">
                  <div className="text-sm font-medium text-purple-600 flex items-center gap-1">
                    <span className="inline-block w-3 h-3 rounded-sm bg-purple-500" />
                    Short
                  </div>
                  <div className="space-y-1.5 text-xs">
                    <LsMetric label="Trades" value={String(lsStats.short.totalTrades)} />
                    <LsMetric label="Win Rate" value={`${(lsStats.short.winRate * 100).toFixed(1)}%`} color={lsStats.short.winRate >= 0.5 ? 'green' : 'red'} />
                    <LsMetric label="Avg Hold" value={`${fmt(lsStats.short.avgHolding, 1)}d`} />
                    <LsMetric label="Expectancy" value={fmt(lsStats.short.expectancy)} color={lsStats.short.expectancy >= 0 ? 'green' : 'red'} />
                    <LsMetric label="Total P&L" value={fmt(lsStats.short.totalPnl)} color={lsStats.short.totalPnl >= 0 ? 'green' : 'red'} />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* PnL distribution + Holding time distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* PnL distribution */}
        {pnlHistData.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border p-4">
            <h3 className="font-semibold text-gray-800 mb-3">P&L Distribution</h3>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={pnlHistData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="label" tick={{ fontSize: 9 }} interval={Math.floor(pnlHistData.length / 6)} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip formatter={(v: number) => `${v} trades`} />
                <Bar dataKey="count" name="Trades" radius={[2, 2, 0, 0]}>
                  {pnlHistData.map((entry, i) => (
                    <Cell key={i} fill={entry.isProfit ? PROFIT_COLOR : LOSS_COLOR} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Holding time distribution */}
        {holdingHistData.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border p-4">
            <h3 className="font-semibold text-gray-800 mb-3">Holding Period Distribution</h3>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={holdingHistData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="label" tick={{ fontSize: 9 }} interval={Math.floor(holdingHistData.length / 6)} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip formatter={(v: number) => `${v} trades`} />
                <Bar dataKey="count" name="Trades" fill="#3b82f6" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* By-asset P&L (horizontal bar, top 20) */}
      {assetPnlData.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border p-4">
          <h3 className="font-semibold text-gray-800 mb-3">Top {assetPnlData.length} Assets by P&L</h3>
          <ResponsiveContainer width="100%" height={Math.max(240, assetPnlData.length * 28)}>
            <BarChart
              data={assetPnlData}
              layout="vertical"
              margin={{ top: 4, right: 16, left: 10, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis type="number" tick={{ fontSize: 10 }} />
              <YAxis type="category" dataKey="asset" tick={{ fontSize: 10 }} width={80} />
              <Tooltip formatter={(v: number) => fmt(v)} />
              <Bar dataKey="pnl" name="P&L" radius={[0, 2, 2, 0]}>
                {assetPnlData.map((entry, i) => (
                  <Cell key={i} fill={entry.pnl >= 0 ? PROFIT_COLOR : LOSS_COLOR} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

/** Long vs Short grouped bar chart */
function LongShortBarChart({ stats }: { stats: { long: ReturnType<typeof computeLongShortStats>['long']; short: ReturnType<typeof computeLongShortStats>['short'] } }) {
  const chartData = [
    {
      label: 'Win Rate',
      long: stats.long ? +(stats.long.winRate * 100).toFixed(1) : 0,
      short: stats.short ? +(stats.short.winRate * 100).toFixed(1) : 0,
      suffix: '%',
    },
    {
      label: 'Expectancy',
      long: stats.long ? +stats.long.expectancy.toFixed(2) : 0,
      short: stats.short ? +stats.short.expectancy.toFixed(2) : 0,
      suffix: '',
    },
    {
      label: 'Avg Hold (d)',
      long: stats.long ? +stats.long.avgHolding.toFixed(1) : 0,
      short: stats.short ? +stats.short.avgHolding.toFixed(1) : 0,
      suffix: '',
    },
    {
      label: 'Total P&L',
      long: stats.long ? +stats.long.totalPnl.toFixed(2) : 0,
      short: stats.short ? +stats.short.totalPnl.toFixed(2) : 0,
      suffix: '',
    },
  ]

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={chartData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis dataKey="label" tick={{ fontSize: 10 }} />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip
          formatter={(value: number, name: string) => {
            const item = chartData.find(d => d.long === value || d.short === value)
            return [`${fmt(value)}${item?.suffix ?? ''}`, name === 'long' ? 'Long' : 'Short']
          }}
        />
        <Bar dataKey="long" name="Long" fill="#3b82f6" radius={[2, 2, 0, 0]} />
        <Bar dataKey="short" name="Short" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Inline metric row for long/short stats */
function LsMetric({ label, value, color }: { label: string; value: string; color?: 'green' | 'red' }) {
  const colorClass = color === 'green' ? 'text-green-600' : color === 'red' ? 'text-red-600' : 'text-gray-800'
  return (
    <div className="flex justify-between items-center">
      <span className="text-gray-500">{label}</span>
      <span className={`font-medium ${colorClass}`}>{value}</span>
    </div>
  )
}

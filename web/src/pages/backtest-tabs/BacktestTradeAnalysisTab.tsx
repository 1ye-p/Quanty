import { MetricCard } from '../../components/ui/MetricCard'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { backtestsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

const PROFIT_COLOR = '#10b981'
const LOSS_COLOR = '#ef4444'

function fmt(n: unknown, digits = 2): string {
  return Number(n ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function BacktestTradeAnalysisTab() {
  const { id } = useParams<{ id: string }>()

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.backtests.tradeAnalysis(id!),
    queryFn: () => backtestsApi.getTradeAnalysis(id!),
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
      <div className="card p-4">
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

      {/* PnL distribution + Holding time distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* PnL distribution */}
        {pnlHistData.length > 0 && (
          <div className="card p-4">
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
          <div className="card p-4">
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
        <div className="card p-4">
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

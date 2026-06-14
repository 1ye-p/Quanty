import { MetricCard } from '../../components/ui/MetricCard'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { backtestsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import type { BacktestFill } from '@/lib/types'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
} from 'recharts'

const COLORS = ['#3b82f6', '#f59e0b', '#8b5cf6', '#ef4444', '#10b981', '#06b6d4', '#ec4899', '#84cc16']

function fmt(n: unknown, digits = 2): string {
  return Number(n ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function BacktestTcaTab() {
  const { id: selectedId } = useParams<{ id: string }>()

  const { data: tcaData, isLoading } = useQuery({
    queryKey: queryKeys.backtests.tca(selectedId!),
    queryFn: () => backtestsApi.getTca(selectedId!),
    enabled: !!selectedId,
  })

  // Fetch fills for per-asset and per-time breakdowns
  const { data: fillsData } = useQuery({
    queryKey: queryKeys.backtests.fills(selectedId!, 0, 10000),
    queryFn: () => backtestsApi.getFills(selectedId!, 0, 10000),
    enabled: !!selectedId,
  })

  if (!selectedId) return null

  if (isLoading) {
    return <div className="text-center text-gray-400 py-12">Loading TCA data...</div>
  }

  if (!tcaData) {
    return <div className="text-center text-gray-400 py-12">No trade data available for cost analysis</div>
  }

  const totalCommission = Number(tcaData.total_commission ?? 0)
  const totalStampDuty = Number(tcaData.total_stamp_duty ?? 0)
  const totalSlippage = Number(tcaData.total_slippage ?? 0)
  const totalCost = Number(tcaData.total_cost ?? 0)
  const numTrades = Number(tcaData.num_trades ?? 0)
  const totalTurnover = Number(tcaData.total_turnover ?? 0)

  // Market impact = total cost - commission - stamp duty - slippage (residual)
  const marketImpact = Math.max(0, totalCost - totalCommission - totalStampDuty - totalSlippage)

  // Cost breakdown pie data
  const costBreakdown = [
    { name: 'Commission', value: totalCommission },
    { name: 'Stamp Duty', value: totalStampDuty },
    { name: 'Slippage', value: totalSlippage },
    { name: 'Market Impact', value: marketImpact },
  ].filter(d => d.value > 0)

  // Compute per-asset cost from fills
  const fills = (fillsData?.items ?? []) as BacktestFill[]
  const assetCostMap = new Map<string, { commission: number; stamp: number; slippage: number; total: number }>()
  const timeCostMap = new Map<string, { commission: number; stamp: number; slippage: number; total: number }>()

  for (const f of fills) {
    const asset = f.asset_id
    const date = f.trade_date
    const commission = f.commission ?? 0
    const stamp = f.stamp_duty ?? 0
    const slippage = f.slippage ?? 0
    const total = commission + stamp + slippage

    // Per asset
    const a = assetCostMap.get(asset) ?? { commission: 0, stamp: 0, slippage: 0, total: 0 }
    a.commission += commission
    a.stamp += stamp
    a.slippage += slippage
    a.total += total
    assetCostMap.set(asset, a)

    // Per month
    const month = date.slice(0, 7) // YYYY-MM
    if (month) {
      const m = timeCostMap.get(month) ?? { commission: 0, stamp: 0, slippage: 0, total: 0 }
      m.commission += commission
      m.stamp += stamp
      m.slippage += slippage
      m.total += total
      timeCostMap.set(month, m)
    }
  }

  // Top 20 assets by cost (horizontal bar)
  const assetCostData = [...assetCostMap.entries()]
    .sort((a, b) => b[1].total - a[1].total)
    .slice(0, 20)
    .map(([asset, c]) => ({
      asset: asset.length > 8 ? asset.slice(0, 8) : asset,
      commission: +c.commission.toFixed(2),
      stamp: +c.stamp.toFixed(2),
      slippage: +c.slippage.toFixed(2),
    }))

  // Cost by time period
  const timeCostData = [...timeCostMap.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([month, c]) => ({
      month,
      commission: +c.commission.toFixed(2),
      stamp: +c.stamp.toFixed(2),
      slippage: +c.slippage.toFixed(2),
    }))

  // Slippage distribution from fills
  const slippages = fills.map(f => Number(f.slippage ?? 0)).filter(s => s !== 0).sort((a, b) => a - b)
  const percentile = (arr: number[], p: number) => {
    if (arr.length === 0) return 0
    const idx = Math.ceil(arr.length * p / 100) - 1
    return arr[Math.max(0, idx)]
  }
  const slipP25 = percentile(slippages, 25)
  const slipP50 = percentile(slippages, 50)
  const slipP75 = percentile(slippages, 75)
  const slipMean = slippages.length > 0 ? slippages.reduce((a, b) => a + b, 0) / slippages.length : 0

  // Slippage distribution histogram
  const slipBins = 20
  const slipMin = slippages.length > 0 ? slippages[0] : 0
  const slipMax = slippages.length > 0 ? slippages[slippages.length - 1] : 1
  const slipRange = slipMax - slipMin || 1
  const slipHistData = slippages.length > 0 ? (() => {
    const bins: { label: string; count: number }[] = []
    for (let i = 0; i < slipBins; i++) {
      const lo = slipMin + (slipRange * i) / slipBins
      const hi = slipMin + (slipRange * (i + 1)) / slipBins
      const count = slippages.filter(s => s >= lo && (i === slipBins - 1 ? s <= hi : s < hi)).length
      bins.push({ label: lo.toFixed(1), count })
    }
    return bins
  })() : []

  return (
    <div className="space-y-6">
      {/* Summary metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard label="Total Cost" value={fmt(totalCost)} />
        <MetricCard label="Cost Ratio" value={`${Number(tcaData.cost_pct_turnover ?? 0).toFixed(4)}%`} />
        <MetricCard label="Trade Count" value={String(numTrades)} />
        <MetricCard label="Avg Cost/Trade" value={fmt(tcaData.cost_per_trade)} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard label="Total Turnover" value={fmt(totalTurnover, 0)} />
        <MetricCard label="Commission" value={fmt(totalCommission)} />
        <MetricCard label="Stamp Duty" value={fmt(totalStampDuty)} />
        <MetricCard label="Slippage" value={fmt(totalSlippage)} />
      </div>

      {/* Cost breakdown pie + Slippage percentiles side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Cost breakdown pie */}
        {costBreakdown.length > 0 && (
          <div className="card p-4">
            <h3 className="font-semibold text-gray-800 mb-3">Cost Breakdown</h3>
            <div className="grid grid-cols-2 gap-4 items-center">
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={costBreakdown}
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  >
                    {costBreakdown.map((_, i) => (
                      <Cell key={i} fill={COLORS[i]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => fmt(v)} />
                </PieChart>
              </ResponsiveContainer>
              <div className="text-sm space-y-2">
                {costBreakdown.map((d, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: COLORS[i] }} />
                    <span className="flex-1 text-gray-600">{d.name}</span>
                    <span className="font-mono text-xs">{fmt(d.value)}</span>
                    <span className="text-gray-400 text-xs">
                      {totalCost > 0 ? `${((d.value / totalCost) * 100).toFixed(1)}%` : '0%'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Slippage analysis */}
        {slippages.length > 0 && (
          <div className="card p-4">
            <h3 className="font-semibold text-gray-800 mb-3">Slippage Distribution</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
              <MetricCard label="Mean" value={fmt(slipMean, 4)} />
              <MetricCard label="P25" value={fmt(slipP25, 4)} />
              <MetricCard label="P50 (Median)" value={fmt(slipP50, 4)} />
              <MetricCard label="P75" value={fmt(slipP75, 4)} />
            </div>
            {slipHistData.length > 0 && (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={slipHistData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="label" tick={{ fontSize: 9 }} interval={Math.floor(slipBins / 6)} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v: number) => `${v} trades`} />
                  <Bar dataKey="count" name="Frequency" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        )}
      </div>

      {/* Cost by asset (horizontal bar) */}
      {assetCostData.length > 0 && (
        <div className="card p-4">
          <h3 className="font-semibold text-gray-800 mb-3">Top {assetCostData.length} Assets by Cost</h3>
          <ResponsiveContainer width="100%" height={Math.max(240, assetCostData.length * 28)}>
            <BarChart
              data={assetCostData}
              layout="vertical"
              margin={{ top: 4, right: 16, left: 10, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis type="number" tick={{ fontSize: 10 }} />
              <YAxis type="category" dataKey="asset" tick={{ fontSize: 10 }} width={80} />
              <Tooltip formatter={(v: number) => fmt(v)} />
              <Legend />
              <Bar dataKey="commission" name="Commission" stackId="a" fill="#3b82f6" />
              <Bar dataKey="stamp" name="Stamp Duty" stackId="a" fill="#f59e0b" />
              <Bar dataKey="slippage" name="Slippage" stackId="a" fill="#8b5cf6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Cost by time period */}
      {timeCostData.length > 0 && (
        <div className="card p-4">
          <h3 className="font-semibold text-gray-800 mb-3">Cost by Month</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={timeCostData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip formatter={(v: number) => fmt(v)} />
              <Legend />
              <Bar dataKey="commission" name="Commission" stackId="a" fill="#3b82f6" />
              <Bar dataKey="stamp" name="Stamp Duty" stackId="a" fill="#f59e0b" />
              <Bar dataKey="slippage" name="Slippage" stackId="a" fill="#8b5cf6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { backtestExtApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { PnLChart, type PnLDataPoint } from '@/components/charts/PnLChart'
import {
  LineChart, Line, Legend,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, AreaChart, Area, ReferenceLine,
} from 'recharts'

function MetricCard({ label, value, sub, warn = false }: {
  label: string; value: string | number; sub?: string; warn?: boolean
}) {
  return (
    <div className={`card text-center py-4 ${warn ? 'border-l-4 border-red-400' : ''}`}>
      <div className={`text-xl font-bold ${warn ? 'text-red-600' : 'text-brand-600'}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  )
}

export function BacktestTearsheetTab() {
  const { id: selectedId } = useParams<{ id: string }>()

  const { data: tearsheet } = useQuery({
    queryKey: queryKeys.backtests.tearsheet(selectedId!),
    queryFn: () => backtestExtApi.tearsheet(selectedId!),
    enabled: !!selectedId,
  })

  const snapshots = (tearsheet as Record<string, unknown>)?.snapshots as Record<string, unknown>[] ?? []

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
          <h3 className="font-semibold text-gray-800 mb-3">NAV & Drawdown Curve</h3>
          <PnLChart data={pnlData} height={280} showDrawdown />
        </div>
      ) : (
        <div className="card text-center text-gray-400 py-12">
          <div className="text-4xl mb-3">Chart</div>
          <div>Tearsheet data loading...</div>
          <div className="text-xs mt-1">Requires complete portfolio_returns storage for NAV curve display</div>
        </div>
      )}

      {/* Benchmark overlay chart */}
      {combinedNav.length > 0 && benchmarkNav.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-800">Benchmark Comparison</h3>
            {(() => {
              const lastPortfolio = combinedNav[combinedNav.length - 1]?.portfolio ?? 1
              const lastBm = benchmarkNav[benchmarkNav.length - 1]?.nav ?? 1
              const excess = (lastPortfolio / lastBm - 1) * 100
              return (
                <div className="text-sm text-gray-600">
                  Excess Return:
                  <span className={`font-mono font-semibold ml-1 ${excess >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                    {excess >= 0 ? '+' : ''}{excess.toFixed(2)}%
                  </span>
                  <span className="text-xs text-gray-400 ml-1">vs {benchmarkAssetId}</span>
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
              <Line dataKey="portfolio" name="Strategy" stroke="#3b82f6" dot={false} strokeWidth={2} />
              <Line dataKey="benchmark" name={benchmarkAssetId || 'Benchmark'} stroke="#94a3b8"
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
            <h3 className="font-semibold text-gray-800 mb-3">Cumulative Excess Return</h3>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={excessData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd"
                  tickFormatter={v => String(v).slice(5)} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${v.toFixed(1)}%`} />
                <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
                <ReferenceLine y={0} stroke="#e5e7eb" />
                <Area type="monotone" dataKey="excess" name="Excess Return" stroke="#10b981" fill="#d1fae5" fillOpacity={0.6} dot={false} />
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
              <h3 className="font-semibold text-gray-800 mb-3">Rolling Tracking Error (20d)</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={rollingData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd"
                    tickFormatter={v => String(v).slice(5)} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${v.toFixed(1)}%`} />
                  <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
                  <Line type="monotone" dataKey="te" name="TE" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">Rolling Information Ratio (20d)</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={rollingData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd"
                    tickFormatter={v => String(v).slice(5)} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v: number) => v.toFixed(3)} />
                  <ReferenceLine y={0} stroke="#e5e7eb" />
                  <Line type="monotone" dataKey="ir" name="IR" stroke="#8b5cf6" dot={false} strokeWidth={1.5} />
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
            <h3 className="font-semibold text-gray-800 mb-3">Up/Down Capture Ratio</h3>
            <div className="grid grid-cols-4 gap-4">
              <MetricCard label="Up Capture" value={`${upCapture.toFixed(1)}%`} sub={`${upCount} up days`} />
              <MetricCard label="Down Capture" value={`${downCapture.toFixed(1)}%`} sub={`${downCount} down days`} warn={downCapture > 100} />
              <MetricCard label="Up Participation" value={String(upCount)} sub="Strategy up when benchmark up" />
              <MetricCard label="Down Participation" value={String(downCount)} sub="Strategy down when benchmark down" />
            </div>
          </div>
        )
      })()}

      {tearsheet && (
        <div className="card">
          <h3 className="font-semibold text-gray-800 mb-3">Raw Data (JSON)</h3>
          <pre className="text-xs text-gray-500 overflow-x-auto bg-gray-50 rounded-lg p-3">
            {JSON.stringify(tearsheet, null, 2).slice(0, 1000)}...
          </pre>
        </div>
      )}
    </div>
  )
}

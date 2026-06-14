import { MetricCard } from '../../components/ui/MetricCard'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { backtestsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
// PositionConcentration import kept for future use when API endpoint is implemented
// import { PositionConcentration, type ConcentrationSnapshot } from '@/components/charts/PositionConcentration'
import {
  LineChart, Line, Legend,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
  Cell, ReferenceLine, CartesianGrid, AreaChart, Area,
  BarChart, Bar, PieChart, Pie,
} from 'recharts'


export function BacktestRiskTab() {
  const { id: selectedId } = useParams<{ id: string }>()
  const [riskWindow, setRiskWindow] = useState(60)

  const { data: riskRollingData } = useQuery({
    queryKey: queryKeys.backtests.riskRolling(selectedId!, riskWindow),
    queryFn: () => backtestsApi.getRiskRolling(selectedId!, riskWindow),
    enabled: !!selectedId,
  })

  const { data: drawdownsData } = useQuery({
    queryKey: queryKeys.backtests.drawdowns(selectedId!),
    queryFn: () => backtestsApi.getDrawdowns(selectedId!),
    enabled: !!selectedId,
  })

  const { data: drawdownTsData } = useQuery({
    queryKey: queryKeys.backtests.drawdownTimeseries(selectedId!),
    queryFn: () => backtestsApi.getDrawdownTimeseries(selectedId!),
    enabled: !!selectedId,
  })

  const { data: returnDistData } = useQuery({
    queryKey: queryKeys.backtests.returnDistribution(selectedId!),
    queryFn: () => backtestsApi.getReturnDistribution(selectedId!),
    enabled: !!selectedId,
  })

  const { data: correlationData } = useQuery({
    queryKey: queryKeys.backtests.correlation(selectedId!),
    queryFn: () => backtestsApi.getCorrelation(selectedId!),
    enabled: !!selectedId,
  })

  const { data: factorExposureData } = useQuery({
    queryKey: queryKeys.backtests.factorExposure(selectedId!),
    queryFn: () => backtestsApi.getFactorExposure(selectedId!),
    enabled: !!selectedId,
  })

  const { data: stressTestData } = useQuery({
    queryKey: queryKeys.backtests.stressTest(selectedId!),
    queryFn: () => backtestsApi.getStressTest(selectedId!),
    enabled: !!selectedId,
  })

  const { data: riskContribData } = useQuery({
    queryKey: queryKeys.backtests.riskContribution(selectedId!),
    queryFn: () => backtestsApi.getRiskContribution(selectedId!),
    enabled: !!selectedId,
  })

  // TODO: Add API endpoint for position concentration data
  // const { data: concentrationData } = useQuery({
  //   queryKey: queryKeys.backtests.positionConcentration(selectedId!),
  //   queryFn: () => backtestsApi.getPositionConcentration(selectedId!),
  //   enabled: !!selectedId,
  // })

  if (!selectedId) return null

  return (
    <div className="space-y-4">
      {riskRollingData ? (
        <>
          {/* Latest metrics cards */}
          {(() => {
            const data = riskRollingData.data as Record<string, unknown>[] | undefined
            const latest = data?.[data.length - 1]
            if (!latest) return null
            return (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <MetricCard label="VaR 95%" value={`${((latest.var_95 as number ?? 0) * 100).toFixed(2)}%`} warn />
                <MetricCard label="CVaR 95%" value={`${((latest.cvar_95 as number ?? 0) * 100).toFixed(2)}%`} warn />
                <MetricCard label="Annualized Vol" value={`${((latest.volatility as number ?? 0) * 100).toFixed(2)}%`} />
                <MetricCard label="Sharpe" value={Number(latest.sharpe_ratio ?? 0).toFixed(3)} />
              </div>
            )
          })()}

          {/* Position Concentration Chart */}
          {/* TODO: Uncomment when position_concentration API endpoint is implemented */}
          {/* {concentrationData?.data && concentrationData.data.length > 0 && (
            <PositionConcentration data={concentrationData.data as ConcentrationSnapshot[]} />
          )} */}

          {/* Window selector */}
          <div className="flex items-center gap-2 text-sm">
            <span className="text-gray-500">Rolling window:</span>
            {[20, 60, 252].map(w => (
              <button
                key={w}
                onClick={() => setRiskWindow(w)}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                  riskWindow === w
                    ? 'bg-brand-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {w}d
              </button>
            ))}
          </div>

          {/* Rolling VaR / CVaR chart */}
          <div className="card">
            <h3 className="font-semibold text-gray-800 mb-3">Rolling VaR / CVaR</h3>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={riskRollingData.data as Record<string, unknown>[]} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="trade_date" tick={{ fontSize: 10 }} interval="preserveStartEnd" tickFormatter={v => String(v).slice(5)} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${(v * 100).toFixed(1)}%`} />
                <Tooltip formatter={(v: number) => `${(v * 100).toFixed(3)}%`} />
                <Legend />
                <Line type="monotone" dataKey="var_95" name="VaR 95%" stroke="#ef4444" dot={false} strokeWidth={1.5} />
                <Line type="monotone" dataKey="cvar_95" name="CVaR 95%" stroke="#dc2626" dot={false} strokeWidth={1.5} strokeDasharray="4 2" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Rolling volatility + Sharpe side by side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">Rolling Volatility</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={riskRollingData.data as Record<string, unknown>[]} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="trade_date" tick={{ fontSize: 10 }} interval="preserveStartEnd" tickFormatter={v => String(v).slice(5)} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${(v * 100).toFixed(1)}%`} />
                  <Tooltip formatter={(v: number) => `${(v * 100).toFixed(3)}%`} />
                  <Line type="monotone" dataKey="volatility" name="Volatility" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">Rolling Sharpe</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={riskRollingData.data as Record<string, unknown>[]} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="trade_date" tick={{ fontSize: 10 }} interval="preserveStartEnd" tickFormatter={v => String(v).slice(5)} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v: number) => v.toFixed(3)} />
                  <ReferenceLine y={0} stroke="#e5e7eb" />
                  <Line type="monotone" dataKey="sharpe_ratio" name="Sharpe" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Drawdown underwater chart */}
          {drawdownTsData && (drawdownTsData.data as Record<string, unknown>[])?.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">Drawdown Underwater Chart</h3>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={drawdownTsData.data as Record<string, unknown>[]} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="trade_date" tick={{ fontSize: 10 }} interval="preserveStartEnd" tickFormatter={v => String(v).slice(5)} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${(v * 100).toFixed(1)}%`} />
                  <Tooltip formatter={(v: number) => `${(v * 100).toFixed(3)}%`} />
                  <Area type="monotone" dataKey="drawdown" name="Drawdown" stroke="#ef4444" fill="#fef2f2" fillOpacity={0.6} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Return distribution histogram */}
          {returnDistData && (returnDistData.data as Record<string, unknown>[])?.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">Return Distribution</h3>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-3">
                <MetricCard label="Mean" value={`${((returnDistData.stats as Record<string, number>)?.mean * 100).toFixed(3)}%`} />
                <MetricCard label="Std Dev" value={`${((returnDistData.stats as Record<string, number>)?.std * 100).toFixed(3)}%`} />
                <MetricCard label="Skewness" value={(returnDistData.stats as Record<string, number>)?.skewness?.toFixed(3) ?? '-'} />
                <MetricCard label="Kurtosis" value={(returnDistData.stats as Record<string, number>)?.kurtosis?.toFixed(3) ?? '-'} />
                <MetricCard label="Range" value={`${((returnDistData.stats as Record<string, number>)?.min * 100).toFixed(2)}% ~ ${((returnDistData.stats as Record<string, number>)?.max * 100).toFixed(2)}%`} />
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={returnDistData.data as Record<string, unknown>[]} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="bin_label" tick={{ fontSize: 9 }} interval={Math.floor((returnDistData.data as unknown[])?.length / 8) || 1} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v: number) => `${v} trades`} />
                  <Bar dataKey="count" name="Frequency" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Drawdown events table */}
          {drawdownsData && (drawdownsData.periods as Record<string, unknown>[])?.length > 0 && (
            <div className="card p-0 overflow-hidden">
              <div className="px-4 pt-3 pb-2 font-semibold text-gray-800 text-sm">Drawdown Events</div>
              <table className="w-full text-xs">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="table-th">#</th>
                    <th className="table-th">Start</th>
                    <th className="table-th">Trough</th>
                    <th className="table-th">Recovery</th>
                    <th className="table-th">Max Drawdown</th>
                    <th className="table-th">Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {(drawdownsData.periods as Record<string, unknown>[]).map((p, i) => (
                    <tr key={i} className="table-row">
                      <td className="table-td font-mono">{String(p.period_id ?? i + 1)}</td>
                      <td className="table-td">{String(p.peak_date ?? '').slice(0, 10)}</td>
                      <td className="table-td">{String(p.trough_date ?? '').slice(0, 10)}</td>
                      <td className="table-td">{p.recovery_date ? String(p.recovery_date).slice(0, 10) : 'Not recovered'}</td>
                      <td className="table-td text-red-600 font-medium">{((p.max_drawdown as number ?? 0) * 100).toFixed(2)}%</td>
                      <td className="table-td">{String(p.duration_days ?? '-')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Correlation Heatmap */}
          {correlationData && (correlationData.assets as string[])?.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">Asset Correlation Matrix</h3>
              <div className="overflow-x-auto">
                <table className="text-xs">
                  <thead>
                    <tr>
                      <th className="px-2 py-1"></th>
                      {(correlationData.assets as string[]).map(a => (
                        <th key={a} className="px-2 py-1 font-mono text-gray-600">{a.slice(0, 6)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(correlationData.assets as string[]).map(row => (
                      <tr key={row}>
                        <td className="px-2 py-1 font-mono text-gray-600">{row.slice(0, 6)}</td>
                        {(correlationData.assets as string[]).map(col => {
                          const val = (correlationData.matrix as Record<string, Record<string, number>>)?.[row]?.[col]
                          return (
                            <td key={col} className="px-2 py-1 text-center" style={{
                              backgroundColor: val == null ? '#f3f4f6'
                                : val > 0 ? `rgba(34,197,94,${Math.abs(val) * 0.8})`
                                : `rgba(239,68,68,${Math.abs(val) * 0.8})`,
                              color: Math.abs(val ?? 0) > 0.5 ? 'white' : '#374151'
                            }}>
                              {val != null ? val.toFixed(2) : '-'}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Factor Exposure */}
          {factorExposureData && (factorExposureData.data as Record<string, unknown>[])?.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">Factor Exposure</h3>
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={factorExposureData.data as Record<string, unknown>[]} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="trade_date" tick={{ fontSize: 10 }} interval="preserveStartEnd" tickFormatter={v => String(v).slice(5)} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Legend />
                  <Area type="monotone" dataKey={(factorExposureData.keys as string[])?.[0] ?? 'momentum_20d'} name="Momentum" stroke="#3b82f6" fill="#dbeafe" fillOpacity={0.6} dot={false} />
                  <Area type="monotone" dataKey={(factorExposureData.keys as string[])?.[1] ?? 'volatility_20d'} name="Volatility" stroke="#f59e0b" fill="#fef3c7" fillOpacity={0.6} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Stress Test */}
          {stressTestData && (stressTestData.scenarios as Record<string, unknown>[])?.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">Stress Test</h3>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart
                  data={(stressTestData.scenarios as Record<string, unknown>[]).map(s => ({
                    ...s,
                    impact_pct: (s.impact as number) * 100,
                  }))}
                  layout="vertical"
                  margin={{ top: 4, right: 16, left: 100, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={v => `${v.toFixed(1)}%`} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={100} />
                  <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} />
                  <Bar dataKey="impact_pct" name="Impact" radius={[0, 4, 4, 0]}>
                    {(stressTestData.scenarios as Record<string, unknown>[]).map((_, i) => (
                      <Cell key={i} fill={i === 5 ? '#8b5cf6' : '#ef4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Risk Contribution Pie */}
          {riskContribData && (riskContribData.contributions as Record<string, unknown>[])?.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-800 mb-3">Risk Contribution</h3>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie
                      data={(riskContribData.contributions as Record<string, unknown>[]).slice(0, 10).map(c => ({
                        name: String(c.asset_id).slice(0, 6),
                        value: Math.abs(c.pct_of_risk as number) * 100,
                      }))}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    >
                      {(riskContribData.contributions as Record<string, unknown>[]).slice(0, 10).map((_, i) => (
                        <Cell key={i} fill={['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1'][i]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="text-sm">
                  <div className="text-gray-500 mb-2">Portfolio Volatility: {((riskContribData.portfolio_volatility as number ?? 0) * 100).toFixed(2)}%</div>
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {(riskContribData.contributions as Record<string, unknown>[]).slice(0, 10).map((c, i) => (
                      <div key={i} className="flex justify-between">
                        <span className="font-mono text-xs">{String(c.asset_id).slice(0, 8)}</span>
                        <span className="text-gray-600">{((c.pct_of_risk as number) * 100).toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="card text-center text-gray-400 py-12">
          <div className="text-4xl mb-3">Chart</div>
          <div className="text-gray-500 mb-2">No risk analysis data available</div>
          <p className="text-xs text-gray-400">Risk data is generated automatically after backtest completion</p>
        </div>
      )}
    </div>
  )
}

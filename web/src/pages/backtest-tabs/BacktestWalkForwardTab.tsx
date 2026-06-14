import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { backtestsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

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

export function BacktestWalkForwardTab() {
  const { id: selectedId } = useParams<{ id: string }>()

  const { data: wfData } = useQuery({
    queryKey: queryKeys.backtests.walkForward(selectedId!),
    queryFn: () => backtestsApi.getWalkForwardFolds(selectedId!),
    enabled: !!selectedId,
    staleTime: 60_000,
  })

  if (!selectedId) return null

  return (
    <div className="space-y-4">
      {!wfData ? (
        <p className="text-gray-400 text-sm">This backtest is not in Walk-Forward mode</p>
      ) : (
        <>
          {/* Aggregated metrics */}
          <div className="grid grid-cols-4 gap-4">
            <MetricCard label="Avg Sharpe" value={(wfData.aggregated.avg_sharpe_ratio ?? 0).toFixed(3)} />
            <MetricCard label="Avg Return" value={`${((wfData.aggregated.avg_total_return ?? 0) * 100).toFixed(2)}%`} />
            <MetricCard label="Max Drawdown" value={`${((wfData.aggregated.avg_max_drawdown ?? 0) * 100).toFixed(2)}%`} warn />
            <MetricCard label="Fold Count" value={String(wfData.n_folds)} />
          </div>

          {/* Fold details table */}
          <div className="card p-0 overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  {['Fold', 'Train', 'OOS', 'Sharpe', 'Return', 'Drawdown', 'Win Rate'].map(h => (
                    <th key={h} className="table-th">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {wfData.folds.map(fold => (
                  <tr key={fold.fold_id} className="table-row">
                    <td className="table-td font-mono">{fold.fold_id + 1}</td>
                    <td className="table-td text-xs">{fold.train_start} ~ {fold.train_end}</td>
                    <td className="table-td text-xs">{fold.test_start} ~ {fold.test_end}</td>
                    <td className="table-td">{(fold.metrics?.sharpe_ratio as number)?.toFixed(3) ?? '-'}</td>
                    <td className="table-td">{((fold.metrics?.total_return as number ?? 0) * 100).toFixed(2)}%</td>
                    <td className="table-td text-red-600">{((fold.metrics?.max_drawdown as number ?? 0) * 100).toFixed(2)}%</td>
                    <td className="table-td">{((fold.metrics?.win_rate as number ?? 0) * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Timeline visualization */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Timeline</h3>
            <div className="relative h-20 bg-gray-100 rounded">
              {wfData.folds.map((fold, i) => {
                const allDates = wfData.folds.flatMap(f => [f.train_start, f.test_end])
                const minDate = new Date(allDates[0])
                const maxDate = new Date(allDates[allDates.length - 1])
                const totalMs = maxDate.getTime() - minDate.getTime()
                const pct = (d: string) => ((new Date(d).getTime() - minDate.getTime()) / totalMs * 100)
                return (
                  <div key={i} className="absolute w-full" style={{ top: `${i * 25}%`, height: '22%' }}>
                    <div className="absolute bg-blue-400 opacity-30 h-full rounded-l"
                      style={{ left: `${pct(fold.train_start)}%`, width: `${pct(fold.train_end) - pct(fold.train_start)}%` }} />
                    <div className="absolute bg-green-500 opacity-60 h-full rounded-r"
                      style={{ left: `${pct(fold.test_start)}%`, width: `${pct(fold.test_end) - pct(fold.test_start)}%` }} />
                  </div>
                )
              })}
            </div>
            <div className="flex gap-4 mt-2 text-xs text-gray-500">
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-400 opacity-30 rounded" />Train</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-green-500 opacity-60 rounded" />OOS</span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

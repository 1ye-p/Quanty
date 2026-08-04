import { MetricCard } from '../../components/ui/MetricCard'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { backtestsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'


export function BacktestWalkForwardTab() {
  const { t } = useTranslation()
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
        <p className="text-gray-400 text-sm">{t('component.walkforward.empty.not_walkforward')}</p>
      ) : (
        <>
          {/* Aggregated metrics */}
          <div className="grid grid-cols-4 gap-4">
            <MetricCard label={t('component.walkforward.metric.avg_sharpe')} value={(wfData.aggregated.avg_sharpe_ratio ?? 0).toFixed(3)} />
            <MetricCard label={t('component.walkforward.metric.avg_return')} value={`${((wfData.aggregated.avg_total_return ?? 0) * 100).toFixed(2)}%`} />
            <MetricCard label={t('component.walkforward.metric.max_drawdown')} value={`${((wfData.aggregated.avg_max_drawdown ?? 0) * 100).toFixed(2)}%`} warn />
            <MetricCard label={t('component.walkforward.metric.fold_count')} value={String(wfData.n_folds)} />
          </div>

          {/* Fold details table */}
          <div className="card p-0 overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  {[
                    t('component.walkforward.table.fold'),
                    t('component.walkforward.table.train'),
                    t('component.walkforward.table.oos'),
                    t('component.walkforward.table.sharpe'),
                    t('component.walkforward.table.return'),
                    t('component.walkforward.table.drawdown'),
                    t('common.metric.win_rate'),
                  ].map((h, idx) => (
                    <th key={idx} className="table-th">{h}</th>
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
            <h3 className="text-sm font-semibold text-gray-700 mb-3">{t('component.walkforward.timeline.title')}</h3>
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
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-400 opacity-30 rounded" />{t('component.walkforward.timeline.train')}</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-green-500 opacity-60 rounded" />{t('component.walkforward.timeline.oos')}</span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

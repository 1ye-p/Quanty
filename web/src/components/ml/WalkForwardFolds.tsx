/**
 * WalkForwardFolds — Table + BarChart comparing IC, Sharpe, win_rate across
 * walk-forward folds.
 */
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts'
import type { MLDiagnosticsFold } from '@/lib/types/ml'
import { formatNum, formatPct } from '@/lib/utils/format'

interface WalkForwardFoldsProps {
  folds: MLDiagnosticsFold[]
}

export function WalkForwardFolds({ folds }: WalkForwardFoldsProps) {
  const { t } = useTranslation()
  const summary = useMemo(() => {
    if (!folds.length) return null
    const meanIc = folds.reduce((s, f) => s + f.ic, 0) / folds.length
    const meanSharpe = folds.reduce((s, f) => s + f.sharpe, 0) / folds.length
    const meanWinRate = folds.reduce((s, f) => s + f.win_rate, 0) / folds.length
    return { meanIc, meanSharpe, meanWinRate }
  }, [folds])

  if (!folds.length) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm bg-gray-50 rounded-lg">
        {t('component.ml.walk_forward_folds.empty')}
      </div>
    )
  }

  const chartData = folds.map(f => ({
    fold: t('component.ml.walk_forward_folds.fold_label', { id: f.fold_id }),
    IC: f.ic,
  }))

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <h3 className="font-semibold text-gray-700 mb-3">{t('component.ml.walk_forward_folds.title')}</h3>

      {/* Bar chart — IC by fold */}
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="fold" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip formatter={(value: number) => [formatNum(value, 4), t('component.ml.walk_forward_folds.tooltip_metric')]} />
          <ReferenceLine y={0} stroke="#9ca3af" />
          <Bar dataKey="IC" radius={[2, 2, 0, 0]}>
            {chartData.map((entry, idx) => (
              <Cell
                key={idx}
                fill={entry.IC >= 0 ? '#10b981' : '#ef4444'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Fold table */}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="py-2 pr-4 font-medium">{t('component.ml.walk_forward_folds.th_fold')}</th>
              <th className="py-2 pr-4 font-medium text-right">{t('component.ml.walk_forward_folds.th_ic')}</th>
              <th className="py-2 pr-4 font-medium text-right">{t('component.ml.walk_forward_folds.th_sharpe')}</th>
              <th className="py-2 font-medium text-right">{t('component.ml.walk_forward_folds.th_win_rate')}</th>
            </tr>
          </thead>
          <tbody>
            {folds.map(f => (
              <tr key={f.fold_id} className="border-b last:border-0">
                <td className="py-2 pr-4 text-gray-700">{f.fold_id}</td>
                <td className={`py-2 pr-4 text-right font-mono ${f.ic >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatNum(f.ic)}
                </td>
                <td className="py-2 pr-4 text-right font-mono text-gray-700">
                  {formatNum(f.sharpe)}
                </td>
                <td className="py-2 text-right font-mono text-gray-700">
                  {formatPct(f.win_rate)}
                </td>
              </tr>
            ))}
          </tbody>
          {summary && (
            <tfoot>
              <tr className="border-t-2 font-medium text-gray-800">
                <td className="py-2 pr-4">{t('component.ml.walk_forward_folds.footer_mean')}</td>
                <td className={`py-2 pr-4 text-right font-mono ${summary.meanIc >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatNum(summary.meanIc)}
                </td>
                <td className="py-2 pr-4 text-right font-mono">
                  {formatNum(summary.meanSharpe)}
                </td>
                <td className="py-2 text-right font-mono">{formatPct(summary.meanWinRate)}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  )
}

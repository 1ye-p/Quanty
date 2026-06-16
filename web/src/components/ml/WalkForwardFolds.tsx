/**
 * WalkForwardFolds — Table + BarChart comparing IC, Sharpe, win_rate across
 * walk-forward folds.
 */
import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts'
import type { MLDiagnosticsFold } from '@/lib/types/ml'

function formatNum(v: number, decimals = 4): string {
  if (!isFinite(v)) return '--'
  return v.toFixed(decimals)
}

function formatPct(v: number): string {
  if (!isFinite(v)) return '--'
  return (v * 100).toFixed(2) + '%'
}

interface WalkForwardFoldsProps {
  folds: MLDiagnosticsFold[]
}

export function WalkForwardFolds({ folds }: WalkForwardFoldsProps) {
  const summary = useMemo(() => {
    if (!folds.length) return null
    const meanIc = folds.reduce((s, f) => s + f.ic, 0) / folds.length
    const meanSharpe = folds.reduce((s, f) => s + f.sharpe, 0) / folds.length
    return { meanIc, meanSharpe }
  }, [folds])

  if (!folds.length) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm bg-gray-50 rounded-lg">
        No walk-forward fold data
      </div>
    )
  }

  const chartData = folds.map(f => ({
    fold: `Fold ${f.fold_id}`,
    IC: f.ic,
  }))

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <h3 className="font-semibold text-gray-700 mb-3">Walk-Forward Stability</h3>

      {/* Bar chart — IC by fold */}
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="fold" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip formatter={(value: number) => [formatNum(value, 4), 'IC']} />
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
              <th className="py-2 pr-4 font-medium">Fold</th>
              <th className="py-2 pr-4 font-medium text-right">IC</th>
              <th className="py-2 pr-4 font-medium text-right">Sharpe</th>
              <th className="py-2 font-medium text-right">Win Rate</th>
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
                <td className="py-2 pr-4">Mean</td>
                <td className={`py-2 pr-4 text-right font-mono ${summary.meanIc >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatNum(summary.meanIc)}
                </td>
                <td className="py-2 pr-4 text-right font-mono">
                  {formatNum(summary.meanSharpe)}
                </td>
                <td className="py-2 text-right font-mono">--</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  )
}

/**
 * Optimization results display with weights table and pie chart.
 */
import { useNavigate } from 'react-router-dom'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import type { OptimizeResult } from '@/lib/api'

const COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
]

interface ResultsTabProps {
  result: OptimizeResult
  optimizer: string
}

export function ResultsTab({ result, optimizer }: ResultsTabProps) {
  const navigate = useNavigate()

  const pieData = Object.entries(result.weights)
    .filter(([, w]) => w > 0.001)
    .map(([asset, weight]) => ({ name: asset, value: Math.round(weight * 10000) / 100 }))

  return (
    <div className="bg-white rounded-xl shadow-sm border p-5 space-y-4">
      <h2 className="font-semibold text-gray-800">Optimization Result</h2>
      <div className="grid grid-cols-3 gap-4 text-center">
        <div className="bg-blue-50 rounded-lg p-3">
          <div className="text-xs text-gray-500">Expected Return</div>
          <div className="text-lg font-bold text-blue-700">
            {(result.expected_return * 100).toFixed(2)}%
          </div>
        </div>
        <div className="bg-green-50 rounded-lg p-3">
          <div className="text-xs text-gray-500">Expected Volatility</div>
          <div className="text-lg font-bold text-green-700">
            {(result.expected_volatility * 100).toFixed(2)}%
          </div>
        </div>
        <div className="bg-purple-50 rounded-lg p-3">
          <div className="text-xs text-gray-500">Sharpe Ratio</div>
          <div className="text-lg font-bold text-purple-700">
            {result.sharpe_ratio.toFixed(3)}
          </div>
        </div>
      </div>

      {result?.metadata?.turnover != null && Number(result.metadata.turnover) > 0 && (
        <div className="text-xs text-gray-500 mt-1">
          Turnover: <span className="font-mono">{(Number(result.metadata.turnover) * 100).toFixed(1)}%</span>
        </div>
      )}

      <div className="grid grid-cols-2 gap-6">
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Weight Allocation</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="py-1">Asset</th>
                <th className="py-1 text-right">Weight</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.weights)
                .sort(([, a], [, b]) => b - a)
                .map(([asset, weight]) => (
                  <tr key={asset} className="border-b border-gray-100">
                    <td className="py-1 font-mono text-xs">{asset}</td>
                    <td className="py-1 text-right">{(weight * 100).toFixed(2)}%</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Weight Distribution</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name"
                  cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name} ${value}%`}>
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number) => `${v}%`} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <button
        className="btn-secondary text-sm w-full mt-2"
        onClick={() => {
          const weights = result.weights as Record<string, number>
          navigate('/strategies', {
            state: {
              openBacktest: true,
              prefill: {
                strategy_id: `opt_${optimizer}_${Date.now().toString(36)}`,
                config: JSON.stringify({
                  strategy_type: 'CustomWeightStrategy',
                  custom_weights: weights,
                }, null, 2),
              },
            },
          })
        }}
      >
        Run backtest with these weights
      </button>
    </div>
  )
}

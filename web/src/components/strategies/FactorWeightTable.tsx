/**
 * FactorWeightTable — Weight configuration table for selected factors.
 *
 * Allows users to set weights for each factor with normalized percentage display.
 */
import { useMemo } from 'react'

interface FactorWeightTableProps {
  factors: string[]
  weights: Record<string, number>
  onChange: (weights: Record<string, number>) => void
}

export function FactorWeightTable({ factors, weights, onChange }: FactorWeightTableProps) {
  const normalizedWeights = useMemo(() => {
    const total = factors.reduce((sum, f) => sum + Math.abs(weights[f] ?? 1), 0)
    if (total === 0) return {}
    return Object.fromEntries(
      factors.map(f => [f, ((Math.abs(weights[f] ?? 1) / total) * 100).toFixed(1)])
    )
  }, [factors, weights])

  const handleWeightChange = (factor: string, value: string) => {
    const num = parseFloat(value)
    if (isNaN(num)) return
    // Clamp to [-10, 10]
    const clamped = Math.max(-10, Math.min(10, num))
    onChange({ ...weights, [factor]: clamped })
  }

  if (factors.length === 0) {
    return (
      <div className="border rounded-lg p-4 bg-gray-50">
        <div className="text-sm text-gray-500">请先选择因子</div>
      </div>
    )
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 text-left">
            <th className="px-3 py-2 font-medium text-gray-600">因子</th>
            <th className="px-3 py-2 font-medium text-gray-600 w-24">权重</th>
            <th className="px-3 py-2 font-medium text-gray-600 w-20">占比</th>
            <th className="px-3 py-2 font-medium text-gray-600 w-16">方向</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {factors.map(factor => {
            const weight = weights[factor] ?? 1
            const normalized = normalizedWeights[factor] ?? '0.0'
            const isPositive = weight >= 0

            return (
              <tr key={factor} className="hover:bg-gray-50">
                <td className="px-3 py-2">
                  <span className="font-mono text-xs">{factor}</span>
                </td>
                <td className="px-3 py-2">
                  <input
                    type="number"
                    min={-10}
                    max={10}
                    step={0.1}
                    value={weight}
                    onChange={e => handleWeightChange(factor, e.target.value)}
                    className="w-20 px-2 py-1 border rounded text-sm text-right"
                  />
                </td>
                <td className="px-3 py-2 text-gray-600">
                  {normalized}%
                </td>
                <td className="px-3 py-2">
                  <span className={`text-xs px-2 py-0.5 rounded ${isPositive ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {isPositive ? '正向' : '反向'}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <div className="px-3 py-2 bg-gray-50 text-xs text-gray-500">
        权重范围: -10 到 10 · 正值 = 因子值越高得分越高 · 负值 = 因子值越低得分越高
      </div>
    </div>
  )
}

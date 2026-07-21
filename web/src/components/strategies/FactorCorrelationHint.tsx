/**
 * FactorCorrelationHint — Shows factor correlation warnings in StrategyBuilder.
 *
 * Auto-computes correlation when 2+ factors are selected.
 * Displays high positive correlation warnings (r > 0.7) suggesting redundant factors.
 * Negative correlation (r < -0.7) is noted as diversification benefit, not a warning.
 * Expandable to show the full correlation matrix.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { factorsApi } from '@/lib/api/factors'

interface FactorCorrelationHintProps {
  factors: string[]
  onRemoveFactor?: (factor: string) => void
}

export function FactorCorrelationHint({ factors, onRemoveFactor }: FactorCorrelationHintProps) {
  const [expanded, setExpanded] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['factors', 'quickCorrelation', factors],
    queryFn: () => factorsApi.quickCorrelation({ factors }),
    enabled: factors.length >= 2,
    staleTime: 60_000,
  })

  if (factors.length < 2) return null

  const warnings = data?.warnings ?? []
  const matrix = data?.correlation_matrix ?? {}
  const factorNames = Object.keys(matrix)

  // Extract high-correlation pairs — only positive correlation is redundancy
  const highCorrPairs: { a: string; b: string; r: number }[] = []
  for (const f1 of factorNames) {
    for (const f2 of factorNames) {
      if (f1 < f2) {
        const r = matrix[f1]?.[f2]
        if (r != null && r > 0.7) {
          highCorrPairs.push({ a: f1, b: f2, r })
        }
      }
    }
  }

  return (
    <div className="border rounded-lg bg-amber-50 p-3">
      <div className="flex items-center justify-between mb-1">
        <div className="text-xs font-medium text-amber-800">
          因子相关性检查
          {isLoading && <span className="ml-2 text-amber-500">计算中...</span>}
        </div>
        {factorNames.length > 0 && (
          <button
            className="text-xs text-amber-600 hover:text-amber-800"
            onClick={() => setExpanded(prev => !prev)}
          >
            {expanded ? '收起矩阵' : '展开矩阵'}
          </button>
        )}
      </div>

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="space-y-1 mt-2">
          {warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-amber-700">
              <span className="mt-0.5 shrink-0">!</span>
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}

      {/* Remove suggestions */}
      {highCorrPairs.length > 0 && onRemoveFactor && (
        <div className="mt-2 space-y-1">
          <div className="text-xs text-amber-600 font-medium">建议移除：</div>
          <div className="flex flex-wrap gap-1">
            {highCorrPairs.map((p, i) => (
              <div key={i} className="flex items-center gap-1">
                <button
                  className="text-xs px-2 py-0.5 rounded bg-amber-200 text-amber-800 hover:bg-amber-300 transition-colors"
                  onClick={() => onRemoveFactor(p.b)}
                  title={`移除 ${p.b} (与 ${p.a} 相关 r=${p.r.toFixed(2)})`}
                >
                  移除 {p.b}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No warnings */}
      {!isLoading && warnings.length === 0 && highCorrPairs.length === 0 && factorNames.length > 0 && (
        <div className="text-xs text-green-700 mt-1">
          所选因子间无高度正相关 (r &le; 0.7)，组合良好。
        </div>
      )}

      {/* Negative correlation note */}
      {!isLoading && (() => {
        const negPairs = factorNames.flatMap((f1, i) =>
          factorNames.slice(i + 1).map(f2 => ({ f1, f2, r: matrix[f1]?.[f2] }))
            .filter(p => p.r != null && p.r < -0.7)
        )
        return negPairs.length > 0 ? (
          <div className="text-xs text-blue-700 mt-1">
            {negPairs.length} 对因子呈高度负相关，有助于分散风险。
          </div>
        ) : null
      })()}

      {/* Expanded matrix */}
      {expanded && factorNames.length > 0 && (
        <div className="mt-3 overflow-x-auto">
          <table className="text-xs border-collapse w-full">
            <thead>
              <tr>
                <th className="py-1 px-1" />
                {factorNames.map(f => (
                  <th
                    key={f}
                    className="py-1 px-1 font-medium text-gray-500 text-center min-w-[48px] max-w-[60px] truncate"
                    title={f}
                  >
                    {f}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {factorNames.map(f1 => (
                <tr key={f1} className="hover:bg-amber-100/50">
                  <td className="py-1 px-2 font-medium text-gray-600 text-right whitespace-nowrap max-w-[80px] truncate" title={f1}>
                    {f1}
                  </td>
                  {factorNames.map(f2 => {
                    const r = matrix[f1]?.[f2]
                    let bg = 'bg-gray-50'
                    let text = 'text-gray-400'
                    if (r === 1.0) {
                      bg = 'bg-amber-100'
                      text = 'text-amber-800 font-bold'
                    } else if (r != null) {
                      const abs = Math.abs(r)
                      if (abs > 0.7) {
                        bg = r > 0 ? 'bg-red-200' : 'bg-blue-200'
                        text = r > 0 ? 'text-red-800 font-medium' : 'text-blue-800 font-medium'
                      } else if (abs > 0.4) {
                        bg = r > 0 ? 'bg-red-100' : 'bg-blue-100'
                        text = 'text-gray-700'
                      }
                    }
                    return (
                      <td key={f2} className="p-0.5">
                        <div
                          className={`rounded py-1 px-1 text-center min-w-[44px] ${bg} ${text}`}
                          title={`${f1} vs ${f2}: ${r?.toFixed(3) ?? 'N/A'}`}
                        >
                          {r != null ? r.toFixed(2) : '-'}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

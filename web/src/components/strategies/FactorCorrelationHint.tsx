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
import { useTranslation } from 'react-i18next'
import { factorsApi } from '@/lib/api/factors'

interface FactorCorrelationHintProps {
  factors: string[]
  onRemoveFactor?: (factor: string) => void
  /** Whether orthogonalization is enabled. */
  orthogonalizeEnabled?: boolean
  /** Called when the orthogonalization toggle changes. */
  onOrthogonalizeChange?: (enabled: boolean) => void
  /** Currently selected base factors for orthogonalization. */
  baseFactors?: string[]
  /** Called when the base factor selection changes. */
  onBaseFactorsChange?: (base: string[]) => void
}

export function FactorCorrelationHint({
  factors,
  onRemoveFactor,
  orthogonalizeEnabled = false,
  onOrthogonalizeChange,
  baseFactors = [],
  onBaseFactorsChange,
}: FactorCorrelationHintProps) {
  const { t } = useTranslation()
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
          {t('component.strategies.factor_correlation.title')}
          {isLoading && <span className="ml-2 text-amber-500">{t('component.strategies.factor_correlation.computing')}</span>}
        </div>
        {factorNames.length > 0 && (
          <button
            className="text-xs text-amber-600 hover:text-amber-800"
            onClick={() => setExpanded(prev => !prev)}
          >
            {expanded ? t('component.strategies.factor_correlation.collapse_matrix') : t('component.strategies.factor_correlation.expand_matrix')}
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
          <div className="text-xs text-amber-600 font-medium">{t('component.strategies.factor_correlation.suggestion_label')}</div>
          <div className="flex flex-wrap gap-1">
            {highCorrPairs.map((p, i) => (
              <div key={i} className="flex items-center gap-1">
                <button
                  className="text-xs px-2 py-0.5 rounded bg-amber-200 text-amber-800 hover:bg-amber-300 transition-colors"
                  onClick={() => onRemoveFactor(p.b)}
                  title={t('component.strategies.factor_correlation.remove_tooltip', { b: p.b, a: p.a, r: p.r.toFixed(2) })}
                >
                  {t('component.strategies.factor_correlation.remove_button', { factor: p.b })}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No warnings */}
      {!isLoading && warnings.length === 0 && highCorrPairs.length === 0 && factorNames.length > 0 && (
        <div className="text-xs text-green-700 mt-1">
          {t('component.strategies.factor_correlation.all_good')}
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
            {t('component.strategies.factor_correlation.negative_note', { count: negPairs.length })}
          </div>
        ) : null
      })()}

      {/* Orthogonalization toggle + base selector */}
      {onOrthogonalizeChange && (
        <div className="mt-3 border-t border-amber-200 pt-2 space-y-2">
          <label className="flex items-center gap-2 text-xs text-amber-800 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={orthogonalizeEnabled}
              onChange={e => onOrthogonalizeChange(e.target.checked)}
              className="rounded border-amber-300"
            />
            <span className="font-medium">{t('component.strategies.orthogonalize.toggle_label')}</span>
            <span className="text-amber-600 font-normal">{t('component.strategies.orthogonalize.toggle_hint')}</span>
          </label>

          {orthogonalizeEnabled && (
            <div className="pl-5 space-y-1">
              <div className="text-xs text-amber-700 font-medium">
                {t('component.strategies.orthogonalize.base_label')}
              </div>
              <div className="flex flex-wrap gap-1">
                {factors.map(f => {
                  const selected = baseFactors.includes(f)
                  return (
                    <button
                      key={f}
                      type="button"
                      onClick={() => {
                        if (!onBaseFactorsChange) return
                        onBaseFactorsChange(
                          selected ? baseFactors.filter(b => b !== f) : [...baseFactors, f],
                        )
                      }}
                      className={`text-xs px-2 py-0.5 rounded transition-colors max-w-[120px] truncate ${
                        selected
                          ? 'bg-amber-500 text-white hover:bg-amber-600'
                          : 'bg-amber-100 text-amber-700 hover:bg-amber-200'
                      }`}
                      title={f}
                    >
                      {f}
                    </button>
                  )
                })}
              </div>
              {baseFactors.length === 0 && (
                <div className="text-xs text-amber-600">
                  {t('component.strategies.orthogonalize.base_empty_hint')}
                </div>
              )}
              {baseFactors.length > 0 && (
                <div className="text-xs text-amber-600">
                  {t('component.strategies.orthogonalize.target_count', {
                    count: factors.length - baseFactors.length,
                    total: factors.length,
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Orthogonalization benefit preview: pairs that would be decoupled */}
      {orthogonalizeEnabled && baseFactors.length > 0 && factorNames.length > 0 && (() => {
        const targetFactors = factorNames.filter(f => !baseFactors.includes(f))
        // high-corr pairs where at least one side is a target (would benefit)
        const benefitPairs = highCorrPairs.filter(
          p => targetFactors.includes(p.a) || targetFactors.includes(p.b),
        )
        return benefitPairs.length > 0 ? (
          <div className="mt-2 text-xs text-green-700">
            {t('component.strategies.orthogonalize.benefit_preview', { count: benefitPairs.length })}
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

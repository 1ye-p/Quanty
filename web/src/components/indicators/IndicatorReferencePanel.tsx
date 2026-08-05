/**
 * IndicatorReferencePanel — Read-only reference panel for technical indicators.
 *
 * Displays indicators grouped by category with search, default params,
 * and click-to-copy DSL syntax. Includes a DSL syntax quick-reference.
 */
import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { indicatorsApi, type IndicatorInfo } from '@/lib/api'

// ── Component ────────────────────────────────────────────────────────────────

export function IndicatorReferencePanel() {
  const { t } = useTranslation()
  const [search, setSearch] = useState('')
  const [copied, setCopied] = useState<string | null>(null)

  const { data: catData } = useQuery({
    queryKey: ['indicator-categories'],
    queryFn: () => indicatorsApi.categories(),
    staleTime: 300_000,
  })

  const { data: indData } = useQuery({
    queryKey: ['indicators'],
    queryFn: () => indicatorsApi.list(),
    staleTime: 300_000,
  })

  // Group indicators by category
  const grouped = useMemo(() => {
    const indicators = indData?.indicators ?? []
    const categories = catData?.categories ?? {}
    const map: Record<string, IndicatorInfo[]> = {}

    // Build category -> indicators mapping
    for (const [cat, info] of Object.entries(categories)) {
      map[cat] = indicators.filter((ind) =>
        info.indicators.includes(ind.name),
      )
    }

    // Filter by search
    if (search) {
      const q = search.toLowerCase()
      for (const cat of Object.keys(map)) {
        map[cat] = map[cat].filter(
          (ind) =>
            ind.name.toLowerCase().includes(q) ||
            (ind.description || '').toLowerCase().includes(q),
        )
      }
    }

    // Remove empty categories
    return Object.fromEntries(
      Object.entries(map).filter(([, inds]) => inds.length > 0),
    )
  }, [indData, catData, search])

  const handleCopy = (indicator: IndicatorInfo) => {
    // Build DSL expression like rsi(14) or sma(20)
    const params = indicator.params ?? []
    const paramStr = params.map((p) => p.default).join(', ')
    const dsl = paramStr
      ? `${indicator.name}(${paramStr})`
      : `${indicator.name}()`
    navigator.clipboard.writeText(dsl)
    setCopied(indicator.name)
    setTimeout(() => setCopied(null), 1500)
  }

  return (
    <div className="h-full flex flex-col text-xs">
      {/* Search */}
      <div className="p-2 border-b">
        <input
          type="text"
          placeholder={t('component.indicators.reference.search_placeholder')}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full px-2 py-1 border rounded text-xs"
        />
      </div>

      {/* Indicator list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-3">
        {Object.entries(grouped).map(([category, indicators]) => (
          <div key={category}>
            <h4 className="font-semibold text-gray-700 mb-1">{category}</h4>
            <div className="space-y-1">
              {indicators.map((ind) => (
                <div
                  key={ind.name}
                  className="flex items-start gap-1 p-1 rounded hover:bg-gray-50 cursor-pointer"
                  onClick={() => handleCopy(ind)}
                  title={t('component.indicators.reference.copy_dsl_title')}
                >
                  <span className="text-blue-600 font-mono shrink-0">
                    {ind.name}
                  </span>
                  <span className="text-gray-500 truncate">
                    {ind.description}
                  </span>
                  {copied === ind.name && (
                    <span className="text-green-600 ml-auto shrink-0">
                      {t('component.indicators.reference.copied')}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* DSL syntax reference */}
      <div className="border-t p-2 bg-gray-50 space-y-1">
        <h4 className="font-semibold text-gray-700">{t('component.indicators.reference.dsl_syntax_title')}</h4>
        <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-[11px]">
          <span className="text-gray-500">{t('component.indicators.reference.dsl_comparison')}</span>
          <span className="font-mono">&gt; &lt; &gt;= &lt;= == !=</span>
          <span className="text-gray-500">{t('component.indicators.reference.dsl_crossover')}</span>
          <span className="font-mono">crosses_above crosses_below</span>
          <span className="text-gray-500">{t('component.indicators.reference.dsl_logic')}</span>
          <span className="font-mono">AND OR NOT</span>
          <span className="text-gray-500">{t('component.indicators.reference.dsl_temporal')}</span>
          <span className="font-mono">for N bars</span>
          <span className="text-gray-500">{t('component.indicators.reference.dsl_price')}</span>
          <span className="font-mono">close open high low volume</span>
        </div>
      </div>
    </div>
  )
}

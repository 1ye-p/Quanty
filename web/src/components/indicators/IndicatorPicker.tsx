/**
 * IndicatorPicker — Browse, search, and select technical indicators.
 *
 * Fetches indicator catalog from API, groups by category with collapsible
 * sections, and lets users add/remove indicators with optional param editing.
 */
import { useState, useMemo, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { indicatorsApi, type IndicatorInfo } from '@/lib/api'
import { DataState } from '@/components/ui/DataState'

// ── Types ────────────────────────────────────────────────────────────────────

interface SelectedIndicator {
  name: string
  params: Record<string, number>
}

export interface IndicatorPickerProps {
  selected: SelectedIndicator[]
  onChange: (selected: SelectedIndicator[]) => void
}

// ── Component ────────────────────────────────────────────────────────────────

export function IndicatorPicker({ selected, onChange }: IndicatorPickerProps) {
  const [search, setSearch] = useState('')
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set())
  const [editingParams, setEditingParams] = useState<string | null>(null)

  // Fetch categories
  const {
    data: catData,
    isLoading: catLoading,
    error: catError,
  } = useQuery({
    queryKey: ['indicator-categories'],
    queryFn: () => indicatorsApi.categories(),
    staleTime: 300_000,
  })

  // Fetch all indicators
  const {
    data: indData,
    isLoading: indLoading,
    error: indError,
  } = useQuery({
    queryKey: ['indicators'],
    queryFn: () => indicatorsApi.list(),
    staleTime: 300_000,
  })

  const isLoading = catLoading || indLoading
  const error = catError || indError

  // Build grouped indicators
  const grouped = useMemo(() => {
    const indicators = indData?.indicators ?? []
    const categories = catData?.categories ?? {}
    const map: Record<string, IndicatorInfo[]> = {}

    for (const cat of Object.keys(categories)) {
      map[cat] = []
    }
    for (const ind of indicators) {
      if (!map[ind.category]) map[ind.category] = []
      map[ind.category].push(ind)
    }
    return map
  }, [catData, indData])

  // Filter by search
  const filteredGrouped = useMemo(() => {
    if (!search.trim()) return grouped
    const q = search.toLowerCase()
    const result: Record<string, IndicatorInfo[]> = {}
    for (const [cat, inds] of Object.entries(grouped)) {
      const filtered = inds.filter(
        (i) =>
          i.name.toLowerCase().includes(q) ||
          i.description.toLowerCase().includes(q),
      )
      if (filtered.length > 0) result[cat] = filtered
    }
    return result
  }, [grouped, search])

  // Selected names set
  const selectedNames = useMemo(
    () => new Set(selected.map((s) => s.name)),
    [selected],
  )

  // Toggle category expand/collapse
  const toggleCategory = useCallback((cat: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev)
      if (next.has(cat)) next.delete(cat)
      else next.add(cat)
      return next
    })
  }, [])

  // Toggle indicator selection
  const toggleIndicator = useCallback(
    (indicator: IndicatorInfo) => {
      if (selectedNames.has(indicator.name)) {
        onChange(selected.filter((s) => s.name !== indicator.name))
      } else {
        const defaultParams: Record<string, number> = {}
        for (const p of indicator.params) {
          defaultParams[p.name] = p.default
        }
        onChange([...selected, { name: indicator.name, params: defaultParams }])
      }
    },
    [selected, selectedNames, onChange],
  )

  // Update param value
  const updateParam = useCallback(
    (indicatorName: string, paramName: string, value: number) => {
      onChange(
        selected.map((s) =>
          s.name === indicatorName
            ? { ...s, params: { ...s.params, [paramName]: value } }
            : s,
        ),
      )
    },
    [selected, onChange],
  )

  // Remove selected indicator
  const removeIndicator = useCallback(
    (name: string) => {
      onChange(selected.filter((s) => s.name !== name))
    },
    [selected, onChange],
  )

  // Get full indicator info by name
  const getIndicatorInfo = useCallback(
    (name: string): IndicatorInfo | undefined => {
      return indData?.indicators.find((i: IndicatorInfo) => i.name === name)
    },
    [indData],
  )

  const categoryCount = Object.keys(filteredGrouped).length

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">技术指标选择</h3>
        {selected.length > 0 && (
          <span className="text-xs text-gray-500">已选 {selected.length} 个</span>
        )}
      </div>

      {/* Search input */}
      <div className="relative">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索指标名称或描述..."
          className="w-full rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm
                     focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
        />
        {search && (
          <button
            onClick={() => setSearch('')}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            aria-label="清除搜索"
          >
            x
          </button>
        )}
      </div>

      {/* Selected tags */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selected.map((s) => {
            const info = getIndicatorInfo(s.name)
            return (
              <span
                key={s.name}
                className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700"
              >
                {s.name}
                {info && info.params.length > 0 && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setEditingParams(editingParams === s.name ? null : s.name)
                    }}
                    className="ml-0.5 text-blue-400 hover:text-blue-600"
                    title="编辑参数"
                  >
                    *
                  </button>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    removeIndicator(s.name)
                  }}
                  className="ml-0.5 text-blue-400 hover:text-blue-600"
                  aria-label={`移除 ${s.name}`}
                >
                  x
                </button>
              </span>
            )
          })}
        </div>
      )}

      {/* Param editor (shown when editing a selected indicator) */}
      {editingParams && (() => {
        const sel = selected.find((s) => s.name === editingParams)
        const info = getIndicatorInfo(editingParams)
        if (!sel || !info || info.params.length === 0) return null
        return (
          <div className="rounded-lg bg-gray-50 border border-gray-200 p-3 space-y-2">
            <div className="text-xs font-medium text-gray-700">{editingParams} 参数</div>
            {info.params.map((p: { name: string; type: string; default: number }) => (
              <div key={p.name} className="flex items-center gap-2">
                <label className="text-xs text-gray-600 w-24 truncate" title={p.name}>
                  {p.name}
                </label>
                <input
                  type="number"
                  value={sel.params[p.name] ?? p.default}
                  onChange={(e) => {
                    const v = parseFloat(e.target.value)
                    if (!isNaN(v)) updateParam(editingParams, p.name, v)
                  }}
                  className="w-20 rounded border border-gray-300 px-2 py-1 text-xs
                             focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
                />
                <span className="text-xs text-gray-400">({p.type})</span>
              </div>
            ))}
          </div>
        )
      })()}

      {/* Indicator list grouped by category */}
      <DataState isLoading={isLoading} error={error} isEmpty={categoryCount === 0} emptyText="暂无指标">
        <div className="max-h-96 overflow-y-auto space-y-1">
          {Object.entries(filteredGrouped).map(([category, indicators]) => {
            const isExpanded = expandedCategories.has(category)
            return (
              <div key={category} className="rounded-lg border border-gray-100">
                {/* Category header */}
                <button
                  onClick={() => toggleCategory(category)}
                  className="w-full flex items-center justify-between px-3 py-2 text-sm font-medium
                             text-gray-700 hover:bg-gray-50 rounded-lg transition-colors"
                >
                  <span>
                    {category}
                    <span className="ml-1.5 text-xs text-gray-400">({indicators.length})</span>
                  </span>
                  <span className="text-gray-400 text-xs">{isExpanded ? '[-]' : '[+]'}</span>
                </button>

                {/* Indicator items */}
                {isExpanded && (
                  <div className="px-2 pb-2 space-y-1">
                    {indicators.map((ind) => {
                      const isSelected = selectedNames.has(ind.name)
                      return (
                        <div
                          key={ind.name}
                          onClick={() => toggleIndicator(ind)}
                          className={`cursor-pointer rounded-lg px-3 py-2 text-sm transition-colors
                            ${isSelected
                              ? 'bg-blue-50 border border-blue-200'
                              : 'hover:bg-gray-50 border border-transparent'
                            }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className={`font-medium ${isSelected ? 'text-blue-700' : 'text-gray-900'}`}>
                              {ind.name}
                            </span>
                            {isSelected && (
                              <span className="text-xs text-blue-500">已选</span>
                            )}
                          </div>
                          <div className="text-xs text-gray-500 mt-0.5">{ind.description}</div>
                          {ind.params.length > 0 && (
                            <div className="text-xs text-gray-400 mt-1">
                              {ind.params.map((p: { name: string; default: number }) => `${p.name}=${p.default}`).join(' / ')}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </DataState>
    </div>
  )
}

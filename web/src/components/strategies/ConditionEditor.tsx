/**
 * ConditionEditor — Visual condition builder for strategy signals.
 *
 * Lets users build conditions without writing DSL manually.
 * Supports AND/OR logic, parentheses grouping, and real-time DSL preview.
 */
import { useState, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { indicatorsApi, type IndicatorInfo } from '@/lib/api'

// ── Types ────────────────────────────────────────────────────────────────────

type Operator = '>' | '<' | '>=' | '<=' | '==' | '!=' | 'crosses_above' | 'crosses_below'

interface ConditionRow {
  id: string
  indicator: string
  operator: Operator
  value: string  // Can be a number or another indicator name
  params: Record<string, number>
}

interface ConditionGroup {
  id: string
  rows: ConditionRow[]
  logic: 'AND' | 'OR'
  parenthesized: boolean
}

export interface ConditionEditorProps {
  /** Label like "买入条件" or "卖出条件" */
  label: string
  /** DSL string value */
  value: string
  /** Callback when DSL changes */
  onChange: (dsl: string) => void
  /** Optional asset ID for preview */
  assetId?: string
}

// ── Helpers ──────────────────────────────────────────────────────────────────

let nextId = 0
const genId = () => `id_${nextId++}`

const OPERATORS: { value: Operator; label: string }[] = [
  { value: '>', label: '>' },
  { value: '<', label: '<' },
  { value: '>=', label: '>=' },
  { value: '<=', label: '<=' },
  { value: '==', label: '==' },
  { value: '!=', label: '!=' },
  { value: 'crosses_above', label: '上穿' },
  { value: 'crosses_below', label: '下穿' },
]

const DEFAULT_PARAMS: Record<string, Record<string, number>> = {
  SMA: { period: 20 },
  EMA: { period: 20 },
  RSI: { period: 14 },
  MACD: { fast: 12, slow: 26, signal: 9 },
  BBANDS: { period: 20, std_dev: 2 },
  ATR: { period: 14 },
  ADX: { period: 14 },
  CCI: { period: 20 },
  STOCH: { k_period: 14, d_period: 3 },
  WILLR: { period: 14 },
  MFI: { period: 14 },
  OBV: {},
  VWAP: {},
}

// ── Parse DSL to groups (simplified parser) ──────────────────────────────────

function parseDsl(dsl: string): ConditionGroup[] {
  if (!dsl.trim()) {
    return [{ id: genId(), rows: [{ id: genId(), indicator: 'SMA', operator: '>', value: '0', params: { period: 20 } }], logic: 'AND', parenthesized: false }]
  }

  // Simple parser for conditions like: SMA(close, 20) > 100 AND RSI(14) < 70
  const groups: ConditionGroup[] = []
  const parts = dsl.split(/\s+(AND|OR)\s+/i)

  let currentLogic: 'AND' | 'OR' = 'AND'
  const rows: ConditionRow[] = []

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i].trim()

    if (part.toUpperCase() === 'AND' || part.toUpperCase() === 'OR') {
      currentLogic = part.toUpperCase() as 'AND' | 'OR'
      continue
    }

    // Parse condition: indicator(params) operator value
    const match = part.match(/^(\w+)(?:\(([^)]*)\))?\s*(>=|<=|!=|>|<|==|crosses_above|crosses_below)\s*(.+)$/)
    if (match) {
      const [, indicator, paramsStr, operator, value] = match
      const params: Record<string, number> = {}

      if (paramsStr) {
        // Parse params like "close, 20" or "14"
        const paramParts = paramsStr.split(',').map(p => p.trim())
        const defaultP = DEFAULT_PARAMS[indicator] || {}
        const keys = Object.keys(defaultP)

        paramParts.forEach((p, idx) => {
          const num = parseFloat(p)
          if (!isNaN(num) && keys[idx]) {
            params[keys[idx]] = num
          }
        })
      }

      rows.push({
        id: genId(),
        indicator,
        operator: operator as Operator,
        value: value.trim(),
        params: { ...DEFAULT_PARAMS[indicator], ...params },
      })
    }
  }

  if (rows.length > 0) {
    groups.push({
      id: genId(),
      rows,
      logic: currentLogic,
      parenthesized: dsl.startsWith('(') && dsl.endsWith(')'),
    })
  }

  return groups.length > 0 ? groups : [{ id: genId(), rows: [{ id: genId(), indicator: 'SMA', operator: '>', value: '0', params: { period: 20 } }], logic: 'AND', parenthesized: false }]
}

// ── Generate DSL from groups ─────────────────────────────────────────────────

function generateDsl(groups: ConditionGroup[]): string {
  const parts: string[] = []

  for (const group of groups) {
    const rowDsls: string[] = []

    for (const row of group.rows) {
      const paramStr = Object.values(row.params).join(', ')
      const indicatorDsl = paramStr ? `${row.indicator}(${paramStr})` : row.indicator
      rowDsls.push(`${indicatorDsl} ${row.operator} ${row.value}`)
    }

    const groupDsl = rowDsls.join(` ${group.logic} `)
    parts.push(group.parenthesized ? `(${groupDsl})` : groupDsl)
  }

  return parts.join(' AND ')
}

// ── Component ────────────────────────────────────────────────────────────────

export function ConditionEditor({ label, value, onChange, assetId }: ConditionEditorProps) {
  const [groups, setGroups] = useState<ConditionGroup[]>(() => parseDsl(value))
  const [isEditingDsl, setIsEditingDsl] = useState(false)
  const [dslText, setDslText] = useState(value)

  // Fetch indicators list
  const { data: indicatorsData } = useQuery({
    queryKey: ['indicators'],
    queryFn: () => indicatorsApi.list(),
    staleTime: 300_000,
  })

  const indicators = indicatorsData?.indicators ?? []

  // Fetch condition stats when assetId is provided
  const { data: stats } = useQuery({
    queryKey: ['condition-stats', value, assetId],
    queryFn: async () => {
      if (!assetId || !value.trim()) return null
      // TODO: Fetch actual OHLCV data for the asset
      const mockData = Array.from({ length: 100 }, (_, i) => ({
        date: `2024-01-${String(i + 1).padStart(2, '0')}`,
        open: 100 + Math.random() * 20,
        high: 105 + Math.random() * 20,
        low: 95 + Math.random() * 20,
        close: 100 + Math.random() * 20,
        volume: 1000000 + Math.random() * 5000000,
      }))
      return indicatorsApi.evaluateCondition({ condition_dsl: value, data: mockData })
    },
    enabled: !!assetId && !!value.trim(),
    staleTime: 30_000,
  })

  // Sync DSL text when value changes externally
  useEffect(() => {
    if (!isEditingDsl) {
      setDslText(value)
      setGroups(parseDsl(value))
    }
  }, [value, isEditingDsl])

  // Update parent when groups change
  const updateGroups = useCallback((newGroups: ConditionGroup[]) => {
    setGroups(newGroups)
    onChange(generateDsl(newGroups))
  }, [onChange])

  // Add a new condition row to a group
  const addRow = useCallback((groupId: string) => {
    updateGroups(groups.map(g =>
      g.id === groupId
        ? { ...g, rows: [...g.rows, { id: genId(), indicator: 'SMA', operator: '>' as Operator, value: '0', params: { period: 20 } }] }
        : g
    ))
  }, [groups, updateGroups])

  // Remove a condition row
  const removeRow = useCallback((groupId: string, rowId: string) => {
    updateGroups(groups.map(g =>
      g.id === groupId
        ? { ...g, rows: g.rows.filter(r => r.id !== rowId) }
        : g
    ).filter(g => g.rows.length > 0))
  }, [groups, updateGroups])

  // Update a row
  const updateRow = useCallback((groupId: string, rowId: string, updates: Partial<ConditionRow>) => {
    updateGroups(groups.map(g =>
      g.id === groupId
        ? { ...g, rows: g.rows.map(r => r.id === rowId ? { ...r, ...updates } : r) }
        : g
    ))
  }, [groups, updateGroups])

  // Toggle group logic
  const toggleGroupLogic = useCallback((groupId: string) => {
    updateGroups(groups.map(g =>
      g.id === groupId
        ? { ...g, logic: g.logic === 'AND' ? 'OR' : 'AND' }
        : g
    ))
  }, [groups, updateGroups])

  // Toggle parentheses
  const toggleParentheses = useCallback((groupId: string) => {
    updateGroups(groups.map(g =>
      g.id === groupId
        ? { ...g, parenthesized: !g.parenthesized }
        : g
    ))
  }, [groups, updateGroups])

  // Add a new group
  const addGroup = useCallback(() => {
    updateGroups([...groups, {
      id: genId(),
      rows: [{ id: genId(), indicator: 'SMA', operator: '>' as Operator, value: '0', params: { period: 20 } }],
      logic: 'AND',
      parenthesized: false,
    }])
  }, [groups, updateGroups])

  // Handle DSL text edit
  const handleDslTextChange = useCallback((text: string) => {
    setDslText(text)
    setGroups(parseDsl(text))
    onChange(text)
  }, [onChange])

  // Get indicator info by name
  const getIndicator = useCallback((name: string): IndicatorInfo | undefined => {
    return indicators.find(i => i.name === name)
  }, [indicators])

  // Get common price fields
  const priceFields = ['close', 'open', 'high', 'low', 'volume', 'amount']

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">{label}</h3>
        <div className="flex items-center gap-2">
          {stats && (
            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
              触发 {stats.hit_count}/{stats.total_bars} ({(stats.hit_rate * 100).toFixed(1)}%)
            </span>
          )}
          <button
            className={`text-xs px-2 py-1 rounded ${isEditingDsl ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            onClick={() => setIsEditingDsl(!isEditingDsl)}
          >
            {isEditingDsl ? '可视化' : 'DSL'}
          </button>
        </div>
      </div>

      {/* DSL Preview */}
      <div className="bg-gray-50 rounded-lg p-3 font-mono text-sm text-gray-700 break-all">
        {value || '<未设置条件>'}
      </div>

      {/* Visual Editor */}
      {!isEditingDsl && (
        <div className="space-y-3">
          {groups.map((group, groupIdx) => (
            <div key={group.id} className="relative">
              {/* Group logic indicator */}
              {groupIdx > 0 && (
                <div className="absolute -top-3 left-4 bg-white px-2 text-xs font-medium text-gray-500 z-10">
                  {group.logic}
                </div>
              )}

              <div className={`border rounded-lg p-3 space-y-2 ${group.parenthesized ? 'border-l-4 border-l-blue-400' : ''}`}>
                {/* Group controls */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <button
                      className={`text-xs px-2 py-1 rounded ${group.logic === 'AND' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}
                      onClick={() => toggleGroupLogic(group.id)}
                    >
                      {group.logic}
                    </button>
                    <button
                      className={`text-xs px-2 py-1 rounded ${group.parenthesized ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600'}`}
                      onClick={() => toggleParentheses(group.id)}
                    >
                      ( )
                    </button>
                  </div>
                  {groups.length > 1 && (
                    <button
                      className="text-xs text-red-500 hover:text-red-700"
                      onClick={() => updateGroups(groups.filter(g => g.id !== group.id))}
                    >
                      删除组
                    </button>
                  )}
                </div>

                {/* Condition rows */}
                {group.rows.map((row) => {
                  const indicatorInfo = getIndicator(row.indicator)
                  const hasParams = indicatorInfo && indicatorInfo.params.length > 0

                  return (
                    <div key={row.id} className="flex items-center gap-2">
                      {/* Indicator dropdown */}
                      <select
                        className="flex-1 rounded border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
                        value={row.indicator}
                        onChange={(e) => {
                          const newIndicator = e.target.value
                          updateRow(group.id, row.id, {
                            indicator: newIndicator,
                            params: DEFAULT_PARAMS[newIndicator] || {},
                          })
                        }}
                      >
                        <optgroup label="价格">
                          {priceFields.map(f => (
                            <option key={f} value={f}>{f}</option>
                          ))}
                        </optgroup>
                        <optgroup label="技术指标">
                          {indicators.map(ind => (
                            <option key={ind.name} value={ind.name}>
                              {ind.name} — {ind.description}
                            </option>
                          ))}
                        </optgroup>
                      </select>

                      {/* Params input (if indicator has params) */}
                      {hasParams && (
                        <input
                          type="text"
                          className="w-16 rounded border border-gray-300 px-2 py-1.5 text-xs focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
                          value={Object.values(row.params).join(',')}
                          onChange={(e) => {
                            const vals = e.target.value.split(',').map(v => parseFloat(v.trim())).filter(v => !isNaN(v))
                            const keys = Object.keys(row.params)
                            const newParams: Record<string, number> = {}
                            keys.forEach((k, i) => { if (vals[i] !== undefined) newParams[k] = vals[i] })
                            updateRow(group.id, row.id, { params: newParams })
                          }}
                          placeholder="参数"
                          title={Object.keys(row.params).join(', ')}
                        />
                      )}

                      {/* Operator dropdown */}
                      <select
                        className="w-20 rounded border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
                        value={row.operator}
                        onChange={(e) => updateRow(group.id, row.id, { operator: e.target.value as Operator })}
                      >
                        {OPERATORS.map(op => (
                          <option key={op.value} value={op.value}>{op.label}</option>
                        ))}
                      </select>

                      {/* Value input */}
                      <input
                        type="text"
                        className="flex-1 rounded border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
                        value={row.value}
                        onChange={(e) => updateRow(group.id, row.id, { value: e.target.value })}
                        placeholder="数值或指标"
                      />

                      {/* Delete button */}
                      <button
                        className="text-gray-400 hover:text-red-500 p-1"
                        onClick={() => removeRow(group.id, row.id)}
                        disabled={group.rows.length === 1}
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  )
                })}

                {/* Add row button */}
                <button
                  className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
                  onClick={() => addRow(group.id)}
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  添加条件
                </button>
              </div>
            </div>
          ))}

          {/* Add group button */}
          <button
            className="w-full py-2 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-500 hover:border-blue-400 hover:text-blue-600 flex items-center justify-center gap-2"
            onClick={addGroup}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            添加条件组 (AND/OR)
          </button>
        </div>
      )}

      {/* DSL Text Editor */}
      {isEditingDsl && (
        <div className="space-y-2">
          <textarea
            className="w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            rows={4}
            value={dslText}
            onChange={(e) => handleDslTextChange(e.target.value)}
            placeholder='SMA(close, 20) > SMA(close, 50) AND RSI(14) < 70'
          />
          <div className="text-xs text-gray-500">
            示例: SMA(close, 20) crosses_above SMA(close, 50) AND RSI(14) &lt; 70
          </div>
        </div>
      )}

      {/* Statistics */}
      {stats && (
        <div className="grid grid-cols-3 gap-2 pt-2 border-t">
          <div className="text-center">
            <div className="text-lg font-semibold text-blue-600">{stats.hit_count}</div>
            <div className="text-xs text-gray-500">触发次数</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold text-gray-700">{stats.total_bars}</div>
            <div className="text-xs text-gray-500">总K线数</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold text-green-600">{(stats.hit_rate * 100).toFixed(1)}%</div>
            <div className="text-xs text-gray-500">触发率</div>
          </div>
        </div>
      )}
    </div>
  )
}
/**
 * IndicatorParamConfig — Configuration panel for technical indicator parameters.
 *
 * Default presets: RSI(14), MACD(12,26,9), MA(20).
 * Per-strategy parameter isolation.
 * Shows parameter inputs when an indicator is selected.
 */
import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'

interface IndicatorDef {
  name: string
  params: { key: string; default: number; min?: number; max?: number }[]
}

const INDICATOR_PRESETS: IndicatorDef[] = [
  {
    name: 'RSI',
    params: [{ key: 'period', default: 14, min: 2, max: 100 }],
  },
  {
    name: 'MACD',
    params: [
      { key: 'fast', default: 12, min: 2, max: 100 },
      { key: 'slow', default: 26, min: 2, max: 200 },
      { key: 'signal', default: 9, min: 2, max: 50 },
    ],
  },
  {
    name: 'MA',
    params: [{ key: 'period', default: 20, min: 2, max: 500 }],
  },
  {
    name: 'EMA',
    params: [{ key: 'period', default: 20, min: 2, max: 500 }],
  },
  {
    name: 'BOLL',
    params: [
      { key: 'period', default: 20, min: 2, max: 200 },
      { key: 'std_dev', default: 2, min: 0.5, max: 5 },
    ],
  },
  {
    name: 'KDJ',
    params: [
      { key: 'k_period', default: 9, min: 2, max: 100 },
      { key: 'd_period', default: 3, min: 2, max: 50 },
    ],
  },
]

interface IndicatorParamConfigProps {
  /** Current indicator specs extracted from DSL conditions */
  activeIndicators?: { name: string; params: Record<string, number> }[]
  /** Called when user changes a parameter value */
  onParamChange?: (indicatorName: string, key: string, value: number) => void
  /** Called to insert DSL snippet into the condition editor */
  onInsertDSL?: (dsl: string) => void
}

export function IndicatorParamConfig({
  activeIndicators = [],
  onParamChange,
  onInsertDSL,
}: IndicatorParamConfigProps) {
  const { t } = useTranslation()
  const [selectedPreset, setSelectedPreset] = useState<string>('')

  const indicatorLabel = (name: string) =>
    t(`component.strategies.indicator_param.indicators.${name}`, { defaultValue: name })
  const paramLabel = (key: string) =>
    t(`component.strategies.indicator_param.params.${key}`, { defaultValue: key })

  // Build a lookup of active indicator params
  const activeMap = new Map<string, Record<string, number>>()
  for (const spec of activeIndicators) {
    activeMap.set(spec.name.toUpperCase(), spec.params)
  }

  const handleInsertPreset = useCallback(
    (preset: IndicatorDef) => {
      const paramStr = preset.params.map(p => String(p.default)).join(',')
      const dsl = `${preset.name}(${paramStr})`
      onInsertDSL?.(dsl)
      setSelectedPreset('')
    },
    [onInsertDSL],
  )

  // Find which presets are currently active in DSL conditions
  const activePresetNames = new Set(
    INDICATOR_PRESETS
      .filter(p => activeMap.has(p.name))
      .map(p => p.name),
  )

  return (
    <div className="border rounded-lg p-3 bg-gray-50">
      <div className="text-xs font-medium text-gray-600 mb-2">{t('component.strategies.indicator_param.title')}</div>

      {/* Quick-insert presets */}
      <div className="flex flex-wrap gap-1 mb-3">
        {INDICATOR_PRESETS.map(preset => {
          const isActive = activePresetNames.has(preset.name)
          return (
            <button
              key={preset.name}
              className={`text-xs px-2 py-1 rounded border transition-colors ${
                isActive
                  ? 'bg-blue-100 border-blue-300 text-blue-700'
                  : 'bg-white border-gray-200 text-gray-600 hover:bg-blue-50 hover:border-blue-200'
              }`}
              onClick={() => {
                if (isActive) {
                  setSelectedPreset(selectedPreset === preset.name ? '' : preset.name)
                } else {
                  handleInsertPreset(preset)
                }
              }}
              title={indicatorLabel(preset.name)}
            >
              {preset.name}
              {isActive && <span className="ml-1 text-blue-400">&#10003;</span>}
            </button>
          )
        })}
      </div>

      {/* Active indicator parameter editors */}
      {activePresetNames.size > 0 && (
        <div className="space-y-2">
          {INDICATOR_PRESETS.filter(p => activePresetNames.has(p.name)).map(preset => {
            const currentParams = activeMap.get(preset.name) ?? {}
            const isExpanded = selectedPreset === preset.name || activePresetNames.size === 1

            return (
              <div key={preset.name} className="bg-white border rounded p-2">
                <button
                  className="flex items-center justify-between w-full text-xs text-left"
                  onClick={() => setSelectedPreset(isExpanded ? '' : preset.name)}
                >
                  <span className="font-medium text-gray-700">{indicatorLabel(preset.name)}</span>
                  <span className="text-gray-400">{isExpanded ? '▲' : '▼'}</span>
                </button>

                {isExpanded && (
                  <div className="grid grid-cols-3 gap-2 mt-2">
                    {preset.params.map(p => {
                      const val = currentParams[p.key] ?? p.default
                      return (
                        <div key={p.key}>
                          <label className="text-[10px] text-gray-500 block">{paramLabel(p.key)}</label>
                          <input
                            type="number"
                            className="input w-full text-xs"
                            value={val}
                            min={p.min}
                            max={p.max}
                            step={1}
                            onChange={e => {
                              const num = parseFloat(e.target.value)
                              if (!isNaN(num)) {
                                onParamChange?.(preset.name, p.key, num)
                              }
                            }}
                          />
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Empty state */}
      {activePresetNames.size === 0 && (
        <div className="text-xs text-gray-400 mt-1">
          {t('component.strategies.indicator_param.empty_hint')}
        </div>
      )}
    </div>
  )
}

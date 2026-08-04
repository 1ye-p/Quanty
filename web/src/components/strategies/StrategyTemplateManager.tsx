/**
 * StrategyTemplateManager — Preset + custom factor template selector.
 *
 * Features:
 * - Preset template dropdown (value / growth / momentum / low_vol)
 * - Load template: populates factor weights in parent
 * - Save current config as custom template (via localStorage)
 * - Custom template list with delete
 */
import { useState, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { factorsApi, type FactorTemplate } from '@/lib/api/factors'

// ── Custom template storage (localStorage) ───────────────────────────────────

const CUSTOM_KEY = 'cquant_custom_factor_templates'

interface CustomTemplate {
  id: string
  name: string
  description: string
  factor_weights: Record<string, number>
  top_n: number
  created_at: string
}

function loadCustomTemplates(): CustomTemplate[] {
  try {
    if (typeof localStorage === 'undefined') return []
    return JSON.parse(localStorage.getItem(CUSTOM_KEY) ?? '[]')
  } catch (e) {
    console.warn('Failed to parse custom templates from localStorage:', e)
    return []
  }
}

function saveCustomTemplates(templates: CustomTemplate[]) {
  if (typeof localStorage === 'undefined') return
  localStorage.setItem(CUSTOM_KEY, JSON.stringify(templates))
}

// ── Component ────────────────────────────────────────────────────────────────

interface Props {
  /** Called when a template is selected — provides factor_weights and top_n. */
  onLoad: (factorWeights: Record<string, number>, topN: number) => void
  /** Current factor weights from the builder (for "save as template"). */
  currentFactorWeights: Record<string, number>
  currentTopN: number
  currentSelectedFactors: string[]
}

export function StrategyTemplateManager({
  onLoad,
  currentFactorWeights,
  currentTopN,
  currentSelectedFactors,
}: Props) {
  const { t } = useTranslation()
  const [mode, setMode] = useState<'preset' | 'custom'>('preset')
  const [customTemplates, setCustomTemplates] = useState<CustomTemplate[]>(loadCustomTemplates)
  const [saveName, setSaveName] = useState('')
  const [saveDesc, setSaveDesc] = useState('')

  // Fetch preset templates from API
  const { data: presetData, isLoading, error } = useQuery({
    queryKey: ['factor-templates'],
    queryFn: () => factorsApi.templates.list(),
    staleTime: 300_000,
  })

  const presets = presetData?.items ?? []

  // Sync custom templates to localStorage (only fires when customTemplates changes)
  useEffect(() => {
    saveCustomTemplates(customTemplates)
  }, [customTemplates])

  const handlePresetSelect = useCallback(
    (tpl: FactorTemplate) => {
      onLoad(tpl.factor_weights, tpl.top_n)
    },
    [onLoad],
  )

  const handleCustomSelect = useCallback(
    (tpl: CustomTemplate) => {
      onLoad(tpl.factor_weights, tpl.top_n)
    },
    [onLoad],
  )

  const handleSave = useCallback(() => {
    if (!saveName.trim()) return
    const newTpl: CustomTemplate = {
      id: `custom_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      name: saveName.trim(),
      description: saveDesc.trim(),
      factor_weights: { ...currentFactorWeights },
      top_n: currentTopN,
      created_at: new Date().toISOString(),
    }
    setCustomTemplates(prev => [newTpl, ...prev])
    setSaveName('')
    setSaveDesc('')
    toast.success(t('component.strategies.factor_template.saved_toast'))
  }, [saveName, saveDesc, currentFactorWeights, currentTopN, t])

  const handleDelete = useCallback((id: string) => {
    setCustomTemplates(prev => prev.filter(t => t.id !== id))
    toast.success(t('component.strategies.factor_template.deleted_toast'))
  }, [t])

  const hasFactors = currentSelectedFactors.length > 0 && Object.keys(currentFactorWeights).length > 0

  return (
    <div className="border rounded-lg p-3 bg-white space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-600">{t('component.strategies.factor_template.title')}</span>
        <div className="flex gap-1">
          <button
            className={`text-[11px] px-2 py-1 rounded transition-colors ${
              mode === 'preset' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
            onClick={() => setMode('preset')}
          >
            {t('component.strategies.factor_template.mode_preset')}
          </button>
          <button
            className={`text-[11px] px-2 py-1 rounded transition-colors ${
              mode === 'custom' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
            onClick={() => setMode('custom')}
          >
            {t('component.strategies.factor_template.mode_custom')}
          </button>
        </div>
      </div>

      {mode === 'preset' && (
        <div className="space-y-2">
          {isLoading && <div className="text-xs text-gray-400">{t('common.loading')}</div>}
          {error && (
            <div className="text-xs text-red-500 py-2">
              {t('component.strategies.factor_template.load_failed', { message: (error as Error).message })}
            </div>
          )}
          {presets.map(tpl => (
            <button
              key={tpl.template_id}
              className="w-full text-left p-2 rounded border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-colors"
              onClick={() => handlePresetSelect(tpl)}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-800">{tpl.name}</span>
                <div className="flex gap-1">
                  {tpl.tags?.map(tag => (
                    <span key={tag} className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
              <div className="text-xs text-gray-500 mt-0.5">{tpl.description}</div>
              <div className="text-[11px] text-gray-400 mt-1 font-mono">
                {Object.entries(tpl.factor_weights)
                  .map(([k, v]) => `${k}:${v > 0 ? '+' : ''}${v}`)
                  .join('  ')}
              </div>
            </button>
          ))}
        </div>
      )}

      {mode === 'custom' && (
        <div className="space-y-3">
          {/* Save current config as template */}
          <div className="border-t pt-3">
            <div className="text-[11px] text-gray-500 mb-2">{t('component.strategies.factor_template.save_current')}</div>
            <div className="flex gap-2 mb-2">
              <input
                className="input flex-1 text-xs"
                placeholder={t('component.strategies.factor_template.name_placeholder')}
                value={saveName}
                onChange={e => setSaveName(e.target.value)}
              />
              <input
                className="input flex-1 text-xs"
                placeholder={t('component.strategies.factor_template.desc_placeholder')}
                value={saveDesc}
                onChange={e => setSaveDesc(e.target.value)}
              />
              <button
                className="text-xs px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={!saveName.trim() || !hasFactors}
                onClick={handleSave}
              >
                {t('common.save')}
              </button>
            </div>
            {!hasFactors && (
              <div className="text-[11px] text-amber-500">{t('component.strategies.factor_template.select_factors_first')}</div>
            )}
          </div>

          {/* Custom template list */}
          {customTemplates.length === 0 ? (
            <div className="text-xs text-gray-400 text-center py-2">{t('component.strategies.factor_template.no_custom')}</div>
          ) : (
            <div className="space-y-2">
              {customTemplates.map(tpl => (
                <div
                  key={tpl.id}
                  className="flex items-start gap-2 p-2 rounded border border-gray-200 hover:border-blue-300 cursor-pointer transition-colors"
                  onClick={() => handleCustomSelect(tpl)}
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-800">{tpl.name}</div>
                    {tpl.description && (
                      <div className="text-xs text-gray-500">{tpl.description}</div>
                    )}
                    <div className="text-[11px] text-gray-400 mt-1 font-mono truncate">
                      {Object.entries(tpl.factor_weights)
                        .map(([k, v]) => `${k}:${v > 0 ? '+' : ''}${v}`)
                        .join('  ')}
                    </div>
                  </div>
                  <button
                    className="text-xs text-red-400 hover:text-red-600 shrink-0 mt-0.5"
                    onClick={e => {
                      e.stopPropagation()
                      handleDelete(tpl.id)
                    }}
                  >
                    {t('common.delete')}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

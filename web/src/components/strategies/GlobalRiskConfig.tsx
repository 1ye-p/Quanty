import { useState } from 'react'
import { useTranslation } from 'react-i18next'

export interface RiskTier {
  threshold: number // config units: negative for SL, positive for TP
  fraction: number // percent of position to close, 0 < f <= 100
}

type SideMode = 'disabled' | 'single' | 'tiered'

interface SideConfig {
  pct: number | null
  tiers: RiskTier[] | null
}

export interface GlobalRiskValue {
  stop_loss_pct?: number | null
  take_profit_pct?: number | null
  stop_loss_tiers?: RiskTier[] | null
  take_profit_tiers?: RiskTier[] | null
  tier_rearm_buffer?: number | null
  // legacy keys (pre dual-side schema), read-only backward compat
  global_stop_loss_pct?: number | null
  global_take_profit_pct?: number | null
  tiers?: RiskTier[] | null
}

interface GlobalRiskConfigProps {
  value: GlobalRiskValue
  onChange: (val: {
    stop_loss_pct: number | null
    take_profit_pct: number | null
    stop_loss_tiers?: RiskTier[] | null
    take_profit_tiers?: RiskTier[] | null
    tier_rearm_buffer?: number | null
  }) => void
}

const MAX_TIERS = 3

const validTiers = (t: RiskTier[] | null | undefined): RiskTier[] | null =>
  t && t.length > 0 ? t : null

/** Read one side's config from props, with legacy-key fallback. */
const readSide = (side: 'sl' | 'tp', value: GlobalRiskValue): SideConfig =>
  side === 'sl'
    ? {
        pct: value.stop_loss_pct ?? value.global_stop_loss_pct ?? null,
        tiers: validTiers(value.stop_loss_tiers) ?? validTiers(value.tiers),
      }
    : { pct: value.take_profit_pct ?? value.global_take_profit_pct ?? null, tiers: validTiers(value.take_profit_tiers) }

const deriveMode = (cfg: SideConfig): SideMode =>
  cfg.tiers ? 'tiered' : cfg.pct != null ? 'single' : 'disabled'

/**
 * One side's tri-state editor (disabled / single / tiered).
 *
 * Thresholds are stored in config units (SL negative, TP positive) but
 * edited as positive percentages. Same-side mutex: tiered mode never
 * writes pct, single mode never writes tiers.
 */
function TierEditor({
  side,
  value,
  onChange,
}: {
  side: 'sl' | 'tp'
  value: SideConfig
  onChange: (v: SideConfig) => void
}) {
  const { t } = useTranslation()
  const isSl = side === 'sl'
  const [mode, setMode] = useState<SideMode>(deriveMode(value))
  const [singleStr, setSingleStr] = useState(value.pct != null ? String(Math.abs(value.pct) * 100) : '')
  const [tiers, setTiers] = useState<RiskTier[]>(
    value.tiers && value.tiers.length > 0
      ? value.tiers.map(tr => ({ threshold: Math.abs(tr.threshold) * 100, fraction: tr.fraction * 100 }))
      : [{ threshold: isSl ? 3 : 10, fraction: 30 }]
  )

  const toPct = (s: string): number | null => {
    if (s === '') return null
    const n = Number(s) / 100
    return isSl ? -n : n
  }

  const emit = (m: SideMode, single: string, t: RiskTier[]) => {
    if (m === 'tiered') {
      onChange({
        pct: null,
        tiers: t
          .filter(tr => tr.threshold > 0 && tr.fraction > 0)
          .map(tr => ({
            threshold: isSl ? -tr.threshold / 100 : tr.threshold / 100,
            fraction: tr.fraction / 100,
          })),
      })
    } else if (m === 'single') {
      onChange({ pct: toPct(single), tiers: null })
    } else {
      onChange({ pct: null, tiers: null })
    }
  }

  const handleModeChange = (m: SideMode) => {
    setMode(m)
    emit(m, singleStr, tiers)
  }

  const handleSingleChange = (v: string) => {
    setSingleStr(v)
    emit(mode, v, tiers)
  }

  const updateTier = (idx: number, patch: Partial<RiskTier>) => {
    const next = tiers.map((tr, i) => (i === idx ? { ...tr, ...patch } : tr))
    setTiers(next)
    emit(mode, singleStr, next)
  }

  const addTier = () => {
    if (tiers.length >= MAX_TIERS) return
    const next = [...tiers, { threshold: isSl ? 5 : 15, fraction: 50 }]
    setTiers(next)
    emit(mode, singleStr, next)
  }

  const removeTier = (idx: number) => {
    const next = tiers.filter((_, i) => i !== idx)
    setTiers(next)
    emit(mode, singleStr, next)
  }

  const titleKey = isSl ? 'common.risk_policy.sl_card_title' : 'common.risk_policy.tp_card_title'
  const singleLabelKey = isSl
    ? 'common.risk_policy.global_stop_loss_label'
    : 'common.risk_policy.global_take_profit_label'
  const singleHintKey = isSl
    ? 'common.risk_policy.global_stop_loss_hint'
    : 'common.risk_policy.global_take_profit_hint'
  const thresholdLabelKey = isSl
    ? 'common.risk_policy.tier_threshold_label'
    : 'common.risk_policy.tp_tier_threshold_label'
  const tiersTitleKey = isSl
    ? 'common.risk_policy.tier_editor_title'
    : 'common.risk_policy.tp_tier_editor_title'
  const tierHintKey = isSl ? 'common.risk_policy.tier_hint' : 'common.risk_policy.tp_tier_hint'
  const radioName = `risk-mode-${side}`

  return (
    <div
      className={`border rounded-lg p-3 space-y-3 ${
        isSl ? 'border-rose-200 bg-rose-50' : 'border-emerald-200 bg-emerald-50'
      }`}
    >
      <h5 className={`text-sm font-medium ${isSl ? 'text-rose-800' : 'text-emerald-800'}`}>
        {t(titleKey)}
      </h5>

      {/* Tri-state mode toggle */}
      <div className="flex gap-4 text-sm">
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input type="radio" name={radioName} checked={mode === 'disabled'} onChange={() => handleModeChange('disabled')} />
          {t('common.risk_policy.mode_disabled')}
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input type="radio" name={radioName} checked={mode === 'single'} onChange={() => handleModeChange('single')} />
          {t('common.risk_policy.mode_single')}
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input type="radio" name={radioName} checked={mode === 'tiered'} onChange={() => handleModeChange('tiered')} />
          {t('common.risk_policy.mode_tiered')}
        </label>
      </div>

      {mode === 'single' && (
        <div>
          <label className="block text-xs text-gray-600 mb-1">
            {t(singleLabelKey)}
            <span
              className="ml-1 text-gray-400 cursor-help"
              title={t(singleHintKey)}
              aria-label={t(singleLabelKey)}
            >
              ⓘ
            </span>
          </label>
          <input
            type="number"
            step={0.5}
            min={0}
            max={isSl ? 100 : 1000}
            placeholder={t('common.risk_policy.placeholder_disabled')}
            value={singleStr}
            onChange={e => handleSingleChange(e.target.value)}
            className="input w-full text-sm"
          />
        </div>
      )}

      {mode === 'tiered' && (
        <div className="space-y-2">
          <div className={`text-xs font-medium ${isSl ? 'text-rose-700' : 'text-emerald-700'}`}>
            {t(tiersTitleKey)}
          </div>
          {tiers.map((tier, idx) => (
            <div key={idx} className="flex items-end gap-2">
              <div className="flex-1">
                <label className="block text-xs text-gray-500 mb-1">
                  {t(thresholdLabelKey)} ({idx + 1})
                </label>
                <input
                  type="number"
                  step={0.5}
                  min={0}
                  max={isSl ? 100 : 1000}
                  value={tier.threshold}
                  onChange={e => updateTier(idx, { threshold: Number(e.target.value) })}
                  className="input w-full text-sm"
                />
              </div>
              <div className="flex-1">
                <label className="block text-xs text-gray-500 mb-1">
                  {t('common.risk_policy.tier_fraction_label')}
                </label>
                <input
                  type="number"
                  step={5}
                  min={1}
                  max={100}
                  value={tier.fraction}
                  onChange={e => updateTier(idx, { fraction: Number(e.target.value) })}
                  className="input w-full text-sm"
                />
              </div>
              <button
                type="button"
                onClick={() => removeTier(idx)}
                disabled={tiers.length <= 1}
                className="btn text-xs px-2 py-1.5 border rounded disabled:opacity-40"
                title={t('common.risk_policy.tier_remove')}
              >
                ✕
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={addTier}
            disabled={tiers.length >= MAX_TIERS}
            className={`text-xs px-2 py-1 border rounded disabled:opacity-40 ${
              isSl
                ? 'text-rose-700 border-rose-300 hover:bg-rose-100'
                : 'text-emerald-700 border-emerald-300 hover:bg-emerald-100'
            }`}
          >
            + {t('common.risk_policy.tier_add')}
          </button>
          <p className="text-xs text-gray-400">{t(tierHintKey)}</p>
        </div>
      )}
    </div>
  )
}

/**
 * Global risk config: dual-card (stop-loss / take-profit) tri-state editor.
 *
 * Each side independently: disabled (pct=null, tiers=null), single (pct=N),
 * or tiered (up to 3 {threshold, fraction} tiers, pct=null — same-side mutex).
 * A single shared rearm buffer applies to both sides.
 */
export function GlobalRiskConfig({ value, onChange }: GlobalRiskConfigProps) {
  const { t } = useTranslation()
  const [sl, setSl] = useState<SideConfig>(readSide('sl', value))
  const [tp, setTp] = useState<SideConfig>(readSide('tp', value))
  const [rearmBuffer, setRearmBuffer] = useState(
    value.tier_rearm_buffer != null ? String(value.tier_rearm_buffer * 100) : '0.5'
  )

  const emit = (slv: SideConfig, tpv: SideConfig, buf: string) => {
    onChange({
      stop_loss_pct: slv.pct,
      take_profit_pct: tpv.pct,
      stop_loss_tiers: slv.tiers,
      take_profit_tiers: tpv.tiers,
      tier_rearm_buffer: buf === '' ? 0.005 : Number(buf) / 100,
    })
  }

  const handleSlChange = (v: SideConfig) => {
    setSl(v)
    emit(v, tp, rearmBuffer)
  }

  const handleTpChange = (v: SideConfig) => {
    setTp(v)
    emit(sl, v, rearmBuffer)
  }

  const handleBufferChange = (v: string) => {
    setRearmBuffer(v)
    emit(sl, tp, v)
  }

  return (
    <div className="border rounded-lg p-3 space-y-3">
      <h4 className="text-sm font-medium text-gray-700">
        {t('common.risk_policy.global_risk_title')}
        <span className="ml-2 text-xs text-gray-400 font-normal">
          {t('common.risk_policy.global_risk_subtitle')}
        </span>
      </h4>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <TierEditor side="sl" value={sl} onChange={handleSlChange} />
        <TierEditor side="tp" value={tp} onChange={handleTpChange} />
      </div>

      {/* Shared rearm buffer (applies to both sides) */}
      <div>
        <label className="block text-xs text-gray-600 mb-1">
          {t('common.risk_policy.rearm_buffer_label')}
          <span
            className="ml-1 text-gray-400 cursor-help"
            title={t('common.risk_policy.rearm_buffer_hint')}
          >
            ⓘ
          </span>
        </label>
        <input
          type="number"
          step={0.1}
          min={0}
          max={50}
          value={rearmBuffer}
          onChange={e => handleBufferChange(e.target.value)}
          className="input w-full text-sm"
        />
      </div>
    </div>
  )
}

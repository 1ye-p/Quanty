import { useState } from 'react'
import { useTranslation } from 'react-i18next'

export interface RiskTier {
  threshold: number // positive percent, e.g. 3 means -3% loss
  fraction: number // percent of position to close, 0 < f <= 100
}

interface GlobalRiskConfigProps {
  value: {
    global_stop_loss_pct?: number | null
    global_take_profit_pct?: number | null
    tiers?: RiskTier[] | null
    tier_rearm_buffer?: number | null
  }
  onChange: (val: {
    global_stop_loss_pct: number | null
    global_take_profit_pct: number | null
    tiers?: RiskTier[] | null
    tier_rearm_buffer?: number | null
  }) => void
}

const MAX_TIERS = 3

/**
 * Global risk config panel for portfolio-wide stop-loss / take-profit.
 *
 * Two modes:
 * - single: one stop-loss threshold, full exit (legacy format, backward compatible)
 * - tiered: up to 3 tiers of {threshold, fraction} + hysteresis rearm buffer
 */
export function GlobalRiskConfig({ value, onChange }: GlobalRiskConfigProps) {
  const { t } = useTranslation()
  const [stopLoss, setStopLoss] = useState(
    value.global_stop_loss_pct != null ? String(Math.abs(value.global_stop_loss_pct) * 100) : ''
  )
  const [takeProfit, setTakeProfit] = useState(
    value.global_take_profit_pct != null ? String(value.global_take_profit_pct * 100) : ''
  )
  const [mode, setMode] = useState<'single' | 'tiered'>(
    value.tiers && value.tiers.length > 0 ? 'tiered' : 'single'
  )
  const [tiers, setTiers] = useState<RiskTier[]>(
    value.tiers && value.tiers.length > 0
      ? value.tiers.map(tr => ({
          threshold: Math.abs(tr.threshold) * 100,
          fraction: tr.fraction * 100,
        }))
      : [{ threshold: 3, fraction: 30 }]
  )
  const [rearmBuffer, setRearmBuffer] = useState(
    value.tier_rearm_buffer != null ? String(value.tier_rearm_buffer * 100) : '0.5'
  )

  const toNum = (s: string): number | null => (s === '' ? null : -Number(s) / 100)
  const toNumPos = (s: string): number | null => (s === '' ? null : Number(s) / 100)

  const emit = (
    nextStopLoss: string,
    nextTakeProfit: string,
    nextMode: 'single' | 'tiered',
    nextTiers: RiskTier[],
    nextBuffer: string
  ) => {
    if (nextMode === 'tiered') {
      onChange({
        global_stop_loss_pct: null,
        global_take_profit_pct: toNumPos(nextTakeProfit),
        tiers: nextTiers
          .filter(tr => tr.threshold > 0 && tr.fraction > 0)
          .map(tr => ({ threshold: -tr.threshold / 100, fraction: tr.fraction / 100 })),
        tier_rearm_buffer: nextBuffer === '' ? 0.005 : Number(nextBuffer) / 100,
      })
    } else {
      onChange({
        global_stop_loss_pct: toNum(nextStopLoss),
        global_take_profit_pct: toNumPos(nextTakeProfit),
        tiers: null,
        tier_rearm_buffer: null,
      })
    }
  }

  const handleStopLossChange = (v: string) => {
    setStopLoss(v)
    emit(v, takeProfit, mode, tiers, rearmBuffer)
  }

  const handleTakeProfitChange = (v: string) => {
    setTakeProfit(v)
    emit(stopLoss, v, mode, tiers, rearmBuffer)
  }

  const handleModeChange = (nextMode: 'single' | 'tiered') => {
    setMode(nextMode)
    emit(stopLoss, takeProfit, nextMode, tiers, rearmBuffer)
  }

  const updateTier = (idx: number, patch: Partial<RiskTier>) => {
    const next = tiers.map((tr, i) => (i === idx ? { ...tr, ...patch } : tr))
    setTiers(next)
    emit(stopLoss, takeProfit, mode, next, rearmBuffer)
  }

  const addTier = () => {
    if (tiers.length >= MAX_TIERS) return
    const next = [...tiers, { threshold: 5, fraction: 50 }]
    setTiers(next)
    emit(stopLoss, takeProfit, mode, next, rearmBuffer)
  }

  const removeTier = (idx: number) => {
    const next = tiers.filter((_, i) => i !== idx)
    setTiers(next)
    emit(stopLoss, takeProfit, mode, next, rearmBuffer)
  }

  const handleBufferChange = (v: string) => {
    setRearmBuffer(v)
    emit(stopLoss, takeProfit, mode, tiers, v)
  }

  return (
    <div className="border rounded-lg p-3 bg-rose-50 space-y-3">
      <h4 className="text-sm font-medium text-rose-800">
        {t('common.risk_policy.global_risk_title')}
        <span className="ml-2 text-xs text-gray-400 font-normal">
          {t('common.risk_policy.global_risk_subtitle')}
        </span>
      </h4>

      {/* Mode toggle */}
      <div className="flex gap-4 text-sm">
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="radio"
            name="risk-mode"
            checked={mode === 'single'}
            onChange={() => handleModeChange('single')}
          />
          {t('common.risk_policy.mode_single')}
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="radio"
            name="risk-mode"
            checked={mode === 'tiered'}
            onChange={() => handleModeChange('tiered')}
          />
          {t('common.risk_policy.mode_tiered')}
        </label>
      </div>

      {mode === 'single' && (
        <div className="grid grid-cols-2 gap-3">
          {/* Global Stop Loss */}
          <div>
            <label className="block text-xs text-gray-600 mb-1">
              {t('common.risk_policy.global_stop_loss_label')}
              <span
                className="ml-1 text-gray-400 cursor-help"
                title={t('common.risk_policy.global_stop_loss_hint')}
                aria-label={t('common.risk_policy.global_stop_loss')}
              >
                ⓘ
              </span>
            </label>
            <input
              type="number"
              step={0.5}
              min={0}
              max={100}
              placeholder={t('common.risk_policy.placeholder_disabled')}
              value={stopLoss}
              onChange={e => handleStopLossChange(e.target.value)}
              className="input w-full text-sm"
            />
          </div>

          {/* Global Take Profit */}
          <div>
            <label className="block text-xs text-gray-600 mb-1">
              {t('common.risk_policy.global_take_profit_label')}
              <span
                className="ml-1 text-gray-400 cursor-help"
                title={t('common.risk_policy.global_take_profit_hint')}
                aria-label={t('common.risk_policy.global_take_profit')}
              >
                ⓘ
              </span>
            </label>
            <input
              type="number"
              step={0.5}
              min={0}
              max={1000}
              placeholder={t('common.risk_policy.placeholder_disabled')}
              value={takeProfit}
              onChange={e => handleTakeProfitChange(e.target.value)}
              className="input w-full text-sm"
            />
          </div>
        </div>
      )}

      {mode === 'tiered' && (
        <div className="space-y-3">
          {/* Take profit still applies in tiered mode */}
          <div>
            <label className="block text-xs text-gray-600 mb-1">
              {t('common.risk_policy.global_take_profit_label')}
              <span
                className="ml-1 text-gray-400 cursor-help"
                title={t('common.risk_policy.global_take_profit_hint')}
                aria-label={t('common.risk_policy.global_take_profit')}
              >
                ⓘ
              </span>
            </label>
            <input
              type="number"
              step={0.5}
              min={0}
              max={1000}
              placeholder={t('common.risk_policy.placeholder_disabled')}
              value={takeProfit}
              onChange={e => handleTakeProfitChange(e.target.value)}
              className="input w-full text-sm"
            />
          </div>

          {/* Tier editor */}
          <div className="space-y-2">
            <div className="text-xs font-medium text-rose-700">
              {t('common.risk_policy.tier_editor_title')}
            </div>
            {tiers.map((tier, idx) => (
              <div key={idx} className="flex items-end gap-2">
                <div className="flex-1">
                  <label className="block text-xs text-gray-500 mb-1">
                    {t('common.risk_policy.tier_threshold_label')} ({idx + 1})
                  </label>
                  <input
                    type="number"
                    step={0.5}
                    min={0}
                    max={100}
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
              className="text-xs px-2 py-1 border rounded text-rose-700 border-rose-300 hover:bg-rose-100 disabled:opacity-40"
            >
              + {t('common.risk_policy.tier_add')}
            </button>
            <p className="text-xs text-gray-400">{t('common.risk_policy.tier_hint')}</p>
          </div>

          {/* Rearm buffer */}
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
      )}
    </div>
  )
}

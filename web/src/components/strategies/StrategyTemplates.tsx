/**
 * StrategyTemplates — Predefined condition templates for quick strategy creation.
 *
 * Renders a grid of template cards; clicking one fills the entry/exit DSL fields.
 */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

// ── Types ──────────────────────────────────────────────────────────────────

export interface StrategyTemplate {
  /** i18n key under component.strategies.templates.items.* */
  key: string
  entry: string[]
  exit: string[]
}

// ── Template data ──────────────────────────────────────────────────────────
// Display name/description are resolved via i18n (templates.items.<key>.{name,description}).

export const STRATEGY_TEMPLATES: StrategyTemplate[] = [
  {
    key: 'ma_cross',
    entry: ['sma(5) crosses_above sma(20)'],
    exit: ['sma(5) crosses_below sma(20)'],
  },
  {
    key: 'rsi_oversold',
    entry: ['rsi(14) < 30 AND close > sma(20)'],
    exit: ['rsi(14) > 70'],
  },
  {
    key: 'macd_golden',
    entry: ['macd(12, 26, 9) crosses_above macd_signal(12, 26, 9)'],
    exit: ['macd(12, 26, 9) crosses_below macd_signal(12, 26, 9)'],
  },
  {
    key: 'bollinger_breakout',
    entry: ['close < bb_lower(20, 2)'],
    exit: ['close > bb_upper(20, 2)'],
  },
  {
    key: 'kdj_golden',
    entry: ['kdj_k(14, 3) crosses_above kdj_d(14, 3)'],
    exit: ['kdj_k(14, 3) crosses_below kdj_d(14, 3)'],
  },
  {
    key: 'volume_breakout',
    entry: ['volume_ratio(5) > 2.0 AND close > sma(20)'],
    exit: ['close < sma(10)'],
  },
  {
    key: 'adx_trend',
    entry: ['adx(14) > 25 AND close > ema(20)'],
    exit: ['adx(14) < 20 OR close < ema(20)'],
  },
  {
    key: 'cci_oversold',
    entry: ['cci(20) > -100 AND cci(20) < 0'],
    exit: ['cci(20) > 100'],
  },
]

// ── Component ──────────────────────────────────────────────────────────────

interface Props {
  onSelect: (template: StrategyTemplate) => void
}

export function StrategyTemplates({ onSelect }: Props) {
  const { t } = useTranslation()
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-gray-700">{t('component.strategies.templates.title')}</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {STRATEGY_TEMPLATES.map((tpl, idx) => (
          <button
            key={tpl.key}
            className="bg-white rounded-xl shadow-sm border p-4 text-left transition-all hover:shadow-md hover:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
            style={{
              borderColor: hoveredIdx === idx ? '#93c5fd' : undefined,
            }}
            onMouseEnter={() => setHoveredIdx(idx)}
            onMouseLeave={() => setHoveredIdx(null)}
            onClick={() => onSelect(tpl)}
          >
            <div className="font-medium text-gray-900 text-sm mb-1">{t(`component.strategies.templates.items.${tpl.key}.name`)}</div>
            <div className="text-xs text-gray-500 mb-3 leading-relaxed">{t(`component.strategies.templates.items.${tpl.key}.description`)}</div>

            {/* DSL preview */}
            <div className="space-y-1">
              <div className="flex items-start gap-1">
                <span className="text-[10px] font-medium text-green-600 mt-0.5 shrink-0">{t('component.strategies.templates.buy_label')}</span>
                <code className="text-[11px] text-gray-600 font-mono break-all leading-snug">
                  {tpl.entry[0]}
                </code>
              </div>
              <div className="flex items-start gap-1">
                <span className="text-[10px] font-medium text-red-600 mt-0.5 shrink-0">{t('component.strategies.templates.sell_label')}</span>
                <code className="text-[11px] text-gray-600 font-mono break-all leading-snug">
                  {tpl.exit[0]}
                </code>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

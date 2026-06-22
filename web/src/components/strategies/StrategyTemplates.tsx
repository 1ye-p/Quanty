/**
 * StrategyTemplates — Predefined condition templates for quick strategy creation.
 *
 * Renders a grid of template cards; clicking one fills the entry/exit DSL fields.
 */
import { useState } from 'react'

// ── Types ──────────────────────────────────────────────────────────────────

export interface StrategyTemplate {
  name: string
  description: string
  entry: string[]
  exit: string[]
}

// ── Template data ──────────────────────────────────────────────────────────

export const STRATEGY_TEMPLATES: StrategyTemplate[] = [
  {
    name: '均线交叉',
    description: '短期均线上穿长期均线买入，下穿卖出',
    entry: ['sma(5) crosses_above sma(20)'],
    exit: ['sma(5) crosses_below sma(20)'],
  },
  {
    name: 'RSI 超卖反弹',
    description: 'RSI 超卖且价格在均线上方时买入，超买时卖出',
    entry: ['rsi(14) < 30 AND close > sma(20)'],
    exit: ['rsi(14) > 70'],
  },
  {
    name: 'MACD 金叉',
    description: 'MACD 金叉买入，死叉卖出',
    entry: ['macd(12, 26, 9) crosses_above macd_signal(12, 26, 9)'],
    exit: ['macd(12, 26, 9) crosses_below macd_signal(12, 26, 9)'],
  },
  {
    name: '布林带突破',
    description: '价格突破布林带下轨买入，突破上轨卖出',
    entry: ['close < bb_lower(20, 2)'],
    exit: ['close > bb_upper(20, 2)'],
  },
  {
    name: 'KDJ 金叉',
    description: 'KDJ K 线上穿 D 线买入，下穿卖出',
    entry: ['kdj_k(14, 3) crosses_above kdj_d(14, 3)'],
    exit: ['kdj_k(14, 3) crosses_below kdj_d(14, 3)'],
  },
  {
    name: '放量突破',
    description: '成交量放大且价格突破 20 日高点时买入',
    entry: ['volume_ratio(5) > 2.0 AND close > sma(20)'],
    exit: ['close < sma(10)'],
  },
  {
    name: 'ADX 趋势跟踪',
    description: 'ADX 强趋势信号，配合均线方向',
    entry: ['adx(14) > 25 AND close > ema(20)'],
    exit: ['adx(14) < 20 OR close < ema(20)'],
  },
  {
    name: 'CCI 超卖反弹',
    description: 'CCI 跌入超卖区后回升买入',
    entry: ['cci(20) > -100 AND cci(20) < 0'],
    exit: ['cci(20) > 100'],
  },
]

// ── Component ──────────────────────────────────────────────────────────────

interface Props {
  onSelect: (template: StrategyTemplate) => void
}

export function StrategyTemplates({ onSelect }: Props) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-gray-700">策略模板</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {STRATEGY_TEMPLATES.map((tpl, idx) => (
          <button
            key={tpl.name}
            className="bg-white rounded-xl shadow-sm border p-4 text-left transition-all hover:shadow-md hover:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
            style={{
              borderColor: hoveredIdx === idx ? '#93c5fd' : undefined,
            }}
            onMouseEnter={() => setHoveredIdx(idx)}
            onMouseLeave={() => setHoveredIdx(null)}
            onClick={() => onSelect(tpl)}
          >
            <div className="font-medium text-gray-900 text-sm mb-1">{tpl.name}</div>
            <div className="text-xs text-gray-500 mb-3 leading-relaxed">{tpl.description}</div>

            {/* DSL preview */}
            <div className="space-y-1">
              <div className="flex items-start gap-1">
                <span className="text-[10px] font-medium text-green-600 mt-0.5 shrink-0">买</span>
                <code className="text-[11px] text-gray-600 font-mono break-all leading-snug">
                  {tpl.entry[0]}
                </code>
              </div>
              <div className="flex items-start gap-1">
                <span className="text-[10px] font-medium text-red-600 mt-0.5 shrink-0">卖</span>
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

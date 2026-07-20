import { useState } from 'react'

interface GlobalRiskConfigProps {
  value: {
    global_stop_loss_pct?: number | null
    global_take_profit_pct?: number | null
  }
  onChange: (val: {
    global_stop_loss_pct: number | null
    global_take_profit_pct: number | null
  }) => void
}

/**
 * Global risk config panel for portfolio-wide stop-loss / take-profit.
 *
 * These thresholds apply to *all* positions and trigger after
 * strategy-level risk controls have already been evaluated.
 *
 * Sign convention:
 * - global_stop_loss_pct: negative value (e.g. -0.05 means stop at -5%)
 * - global_take_profit_pct: positive value (e.g. 0.20 means take profit at +20%)
 */
export function GlobalRiskConfig({ value, onChange }: GlobalRiskConfigProps) {
  const [stopLoss, setStopLoss] = useState(
    value.global_stop_loss_pct != null ? String(Math.abs(value.global_stop_loss_pct) * 100) : ''
  )
  const [takeProfit, setTakeProfit] = useState(
    value.global_take_profit_pct != null ? String(value.global_take_profit_pct * 100) : ''
  )

  const toNum = (s: string): number | null => (s === '' ? null : -Number(s) / 100)
  const toNumPos = (s: string): number | null => (s === '' ? null : Number(s) / 100)

  const handleStopLossChange = (value: string) => {
    setStopLoss(value)
    onChange({
      global_stop_loss_pct: toNum(value),
      global_take_profit_pct: toNumPos(takeProfit),
    })
  }

  const handleTakeProfitChange = (value: string) => {
    setTakeProfit(value)
    onChange({
      global_stop_loss_pct: toNum(stopLoss),
      global_take_profit_pct: toNumPos(value),
    })
  }

  return (
    <div className="border rounded-lg p-3 bg-rose-50 space-y-3">
      <h4 className="text-sm font-medium text-rose-800">
        全局止盈止损
        <span className="ml-2 text-xs text-gray-400 font-normal">
          在策略级风控之后生效，覆盖所有持仓
        </span>
      </h4>

      <div className="grid grid-cols-2 gap-3">
        {/* Global Stop Loss */}
        <div>
          <label className="block text-xs text-gray-600 mb-1">
            全局止损 (%)
            <span
              className="ml-1 text-gray-400 cursor-help"
              title="当任意持仓亏损超过此比例时强制平仓。例如输入 5 表示 -5% 止损。"
              aria-label="止损说明"
            >
              ⓘ
            </span>
          </label>
          <input
            type="number"
            step={0.5}
            min={0}
            max={100}
            placeholder="不启用"
            value={stopLoss}
            onChange={e => handleStopLossChange(e.target.value)}
            className="input w-full text-sm"
          />
        </div>

        {/* Global Take Profit */}
        <div>
          <label className="block text-xs text-gray-600 mb-1">
            全局止盈 (%)
            <span
              className="ml-1 text-gray-400 cursor-help"
              title="当任意持仓盈利超过此比例时强制平仓。例如输入 20 表示 +20% 止盈。"
              aria-label="止盈说明"
            >
              ⓘ
            </span>
          </label>
          <input
            type="number"
            step={0.5}
            min={0}
            max={1000}
            placeholder="不启用"
            value={takeProfit}
            onChange={e => handleTakeProfitChange(e.target.value)}
            className="input w-full text-sm"
          />
        </div>
      </div>
    </div>
  )
}

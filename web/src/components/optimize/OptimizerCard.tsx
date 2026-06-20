/**
 * Optimizer configuration card: optimizer type, risk-free rate, cost params,
 * expected returns table, and the optimize button.
 */
import { useState } from 'react'
import type { ViewSpec } from '@/lib/api'
import { BlackLittermanTab } from './BlackLittermanTab'

type OptimizerType = 'mean_variance' | 'risk_parity' | 'cost_aware' | 'black_litterman'

interface OptimizerCardProps {
  optimizer: OptimizerType
  onOptimizerChange: (val: OptimizerType) => void
  longOnly: boolean
  onLongOnlyChange: (val: boolean) => void
  riskFreeRate: string
  onRiskFreeRateChange: (val: string) => void
  costRate: string
  onCostRateChange: (val: string) => void
  turnoverPenalty: string
  onTurnoverPenaltyChange: (val: string) => void
  // Expected returns
  expectedReturnsMap: Record<string, number>
  onExpectedReturnsMapChange: (map: Record<string, number>) => void
  mlFetching: boolean
  mlPredictions: { date: string | null; predictions: Record<string, number> } | undefined
  onImportMl: () => void
  // Black-Litterman
  blViews: ViewSpec[]
  onBlViewsChange: (views: ViewSpec[]) => void
  blTau: number
  onBlTauChange: (tau: number) => void
  // Mutations
  onOptimize: () => void
  isOptimizing: boolean
  optError: Error | null
  hasCovResult: boolean
  // Children slot for constraints toggle + ConstraintsTab
  children?: React.ReactNode
}

export function OptimizerCard({
  optimizer, onOptimizerChange,
  longOnly, onLongOnlyChange,
  riskFreeRate, onRiskFreeRateChange,
  costRate, onCostRateChange,
  turnoverPenalty, onTurnoverPenaltyChange,
  expectedReturnsMap, onExpectedReturnsMapChange,
  mlFetching, mlPredictions, onImportMl,
  blViews, onBlViewsChange, blTau, onBlTauChange,
  onOptimize, isOptimizing, optError, hasCovResult,
  children,
}: OptimizerCardProps) {
  const [returnsText, setReturnsText] = useState('')

  return (
    <div className="bg-white rounded-xl shadow-sm border p-5 space-y-4">
      <h2 className="font-semibold text-gray-800">优化器配置</h2>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">优化器类型</label>
          <select className="input w-full" value={optimizer} onChange={e => onOptimizerChange(e.target.value as any)}>
            <option value="mean_variance">mean_variance — 均值方差</option>
            <option value="risk_parity">risk_parity — 风险平价</option>
            <option value="cost_aware">cost_aware — 成本感知</option>
            <option value="black_litterman">black_litterman — Black-Litterman</option>
          </select>
        </div>
        <div className="flex items-end gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={longOnly} onChange={e => onLongOnlyChange(e.target.checked)} />
            仅做多 (Long Only)
          </label>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">无风险利率</label>
          <input type="number" className="input w-full" value={riskFreeRate}
            onChange={e => onRiskFreeRateChange(e.target.value)} step={0.001} />
        </div>
        {optimizer === 'cost_aware' && (
          <>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">交易成本率</label>
              <input type="number" className="input w-full" value={costRate}
                onChange={e => onCostRateChange(e.target.value)} step={0.0001} min={0} />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">换手惩罚</label>
              <input type="number" className="input w-full" value={turnoverPenalty}
                onChange={e => onTurnoverPenaltyChange(e.target.value)} step={0.0001} min={0} />
            </div>
          </>
        )}
      </div>

      {/* Advanced constraints slot */}
      {children}

      {/* Black-Litterman views */}
      {optimizer === 'black_litterman' && hasCovResult && Object.keys(expectedReturnsMap).length > 0 && (
        <BlackLittermanTab
          assets={Object.keys(expectedReturnsMap)}
          views={blViews}
          onViewsChange={onBlViewsChange}
          tau={blTau}
          onTauChange={onBlTauChange}
        />
      )}

      {/* Expected Returns (hidden for black_litterman — BL derives from views) */}
      {optimizer !== 'black_litterman' && (hasCovResult && Object.keys(expectedReturnsMap).length > 0 ? (
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium text-gray-700">预期年化收益率（%）</label>
            <div className="flex items-center gap-2">
              <button type="button"
                onClick={() => {
                  const input = prompt('批量填充预期收益率（%）:', '10')
                  if (input === null) return
                  const val = Number(input)
                  if (!isNaN(val)) {
                    onExpectedReturnsMapChange(
                      Object.fromEntries(Object.keys(expectedReturnsMap).map(k => [k, val / 100]))
                    )
                  }
                }}
                className="text-xs text-brand-600 hover:underline"
              >
                批量填充
              </button>
              <button type="button"
                onClick={onImportMl}
                disabled={mlFetching || !mlPredictions?.predictions || !Object.keys(mlPredictions.predictions).length}
                title={mlPredictions?.date ? `来自 ${mlPredictions.date}` : '无 ML 预测数据'}
                className="text-xs text-purple-600 hover:underline disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {mlFetching ? '加载…' : '导入 ML 预测'}
              </button>
              <button type="button"
                onClick={() => onExpectedReturnsMapChange(
                  Object.fromEntries(Object.keys(expectedReturnsMap).map(k => [k, 0]))
                )}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                清零
              </button>
            </div>
          </div>
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="table-th text-left">资产代码</th>
                  <th className="table-th text-right">预期年化收益率 (%)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(expectedReturnsMap).map(([asset, ret]) => (
                  <tr key={asset} className="border-t hover:bg-gray-50">
                    <td className="px-3 py-1.5 font-mono text-xs text-gray-700">{asset}</td>
                    <td className="px-3 py-1.5">
                      <input type="number" step={0.1}
                        value={ret * 100}
                        onChange={e => {
                          const val = Number(e.target.value)
                          if (isNaN(val)) return
                          onExpectedReturnsMapChange({ ...expectedReturnsMap, [asset]: val / 100 })
                        }}
                        className="w-full text-right border rounded px-2 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500"
                        placeholder="0"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            risk_parity 优化器不使用预期收益，均值方差优化器需要设置。
          </p>
          <details className="mt-2"
            onToggle={e => {
              if ((e.target as HTMLDetailsElement).open) {
                setReturnsText(
                  Object.entries(expectedReturnsMap)
                    .map(([a, v]) => `${a}, ${v.toFixed(4)}`)
                    .join('\n')
                )
              }
            }}
          >
            <summary className="text-xs text-gray-400 cursor-pointer">
              高级：文本模式输入（编辑后将覆盖表格中对应资产的值）
            </summary>
            <textarea rows={4} value={returnsText}
              onChange={e => {
                setReturnsText(e.target.value)
                const map: Record<string, number> = {}
                for (const line of e.target.value.split('\n').filter(Boolean)) {
                  const [a, v] = line.split(',').map(s => s.trim())
                  if (a && v) map[a] = Number(v)
                }
                onExpectedReturnsMapChange(
                  Object.fromEntries(
                    Object.keys(expectedReturnsMap).map(a => [a, map[a] !== undefined ? map[a] : expectedReturnsMap[a]])
                  )
                )
              }}
              placeholder="asset_id, expected_return (小数形式，如 0.10 表示10%)"
              className="mt-1 w-full font-mono text-xs border rounded p-2 focus:outline-none"
            />
          </details>
        </div>
      ) : (
        <div className="p-3 bg-gray-50 border rounded-lg text-sm text-gray-500">
          请先完成上方的协方差矩阵计算，资产列表将自动填入预期收益表格。
        </div>
      )
      )}

      <button className="btn-primary" onClick={onOptimize}
        disabled={isOptimizing || !hasCovResult}>
        {isOptimizing ? '优化中...' : '运行优化'}
      </button>
      {optError && (
        <div className="text-red-600 text-sm">{String(optError)}</div>
      )}
    </div>
  )
}

/**
 * Optimizer configuration card: optimizer type, risk-free rate, cost params,
 * expected returns table, and the optimize button.
 */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation()

  return (
    <div className="bg-white rounded-xl shadow-sm border p-5 space-y-4">
      <h2 className="font-semibold text-gray-800">{t('component.optimize.optimizer.title')}</h2>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">{t('component.optimize.optimizer.optimizer_type')}</label>
          <select className="input w-full" value={optimizer} onChange={e => onOptimizerChange(e.target.value as any)}>
            <option value="mean_variance">{t('component.optimize.optimizer.type_mean_variance')}</option>
            <option value="risk_parity">{t('component.optimize.optimizer.type_risk_parity')}</option>
            <option value="cost_aware">{t('component.optimize.optimizer.type_cost_aware')}</option>
            <option value="black_litterman">{t('component.optimize.optimizer.type_black_litterman')}</option>
          </select>
        </div>
        <div className="flex items-end gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={longOnly} onChange={e => onLongOnlyChange(e.target.checked)} />
            {t('component.optimize.optimizer.long_only')}
          </label>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">{t('component.optimize.optimizer.risk_free_rate')}</label>
          <input type="number" className="input w-full" value={riskFreeRate}
            onChange={e => onRiskFreeRateChange(e.target.value)} step={0.001} />
        </div>
        {optimizer === 'cost_aware' && (
          <>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">{t('component.optimize.optimizer.cost_rate')}</label>
              <input type="number" className="input w-full" value={costRate}
                onChange={e => onCostRateChange(e.target.value)} step={0.0001} min={0} />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">{t('component.optimize.optimizer.turnover_penalty')}</label>
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
            <label className="text-sm font-medium text-gray-700">{t('component.optimize.optimizer.expected_returns_title')}</label>
            <div className="flex items-center gap-2">
              <button type="button"
                onClick={() => {
                  const input = prompt(t('component.optimize.optimizer.bulk_fill_prompt'), '10')
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
                {t('component.optimize.optimizer.bulk_fill')}
              </button>
              <button type="button"
                onClick={onImportMl}
                disabled={mlFetching || !mlPredictions?.predictions || !Object.keys(mlPredictions.predictions).length}
                title={mlPredictions?.date ? t('component.optimize.optimizer.import_ml_tooltip_date', { date: mlPredictions.date }) : t('component.optimize.optimizer.import_ml_tooltip_empty')}
                className="text-xs text-purple-600 hover:underline disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {mlFetching ? t('component.optimize.optimizer.import_ml_loading') : t('component.optimize.optimizer.import_ml')}
              </button>
              <button type="button"
                onClick={() => onExpectedReturnsMapChange(
                  Object.fromEntries(Object.keys(expectedReturnsMap).map(k => [k, 0]))
                )}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                {t('component.optimize.optimizer.reset_zero')}
              </button>
            </div>
          </div>
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="table-th text-left">{t('component.optimize.optimizer.col_asset_code')}</th>
                  <th className="table-th text-right">{t('component.optimize.optimizer.col_expected_annual_return')}</th>
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
            {t('component.optimize.optimizer.expected_returns_hint')}
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
              {t('component.optimize.optimizer.advanced_text_mode')}
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
              placeholder={t('component.optimize.optimizer.textarea_placeholder')}
              className="mt-1 w-full font-mono text-xs border rounded p-2 focus:outline-none"
            />
          </details>
        </div>
      ) : (
        <div className="p-3 bg-gray-50 border rounded-lg text-sm text-gray-500">
          {t('component.optimize.optimizer.cov_first_hint')}
        </div>
      )
      )}

      <button className="btn-primary" onClick={onOptimize}
        disabled={isOptimizing || !hasCovResult}>
        {isOptimizing ? t('component.optimize.optimizer.optimizing') : t('component.optimize.optimizer.run_optimize')}
      </button>
      {optError && (
        <div className="text-red-600 text-sm">{String(optError)}</div>
      )}
    </div>
  )
}

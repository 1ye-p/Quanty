/**
 * Strategy config preview card.
 * Parses JSON config and displays key parameters in a readable format.
 */
import { useMemo } from 'react'

interface StrategyPreviewProps {
  configText: string
}

const MARKET_LABELS: Record<string, string> = { CN: 'A-Share', US: 'US', HK: 'HK' }
const ADJ_LABELS: Record<string, string> = { forward: 'Forward', backward: 'Backward', none: 'None' }
const REBALANCE_LABELS: Record<string, string> = { '1d': 'Daily', '5d': 'Weekly', '20d': 'Monthly' }

export function StrategyPreview({ configText }: StrategyPreviewProps) {
  const config = useMemo(() => {
    try { return JSON.parse(configText) } catch { return null }
  }, [configText])

  if (!config) return (
    <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-600">
      Invalid JSON configuration
    </div>
  )

  const factors: string[] = config.factors ?? []
  const riskLimits = config.risk_limits ?? {}
  const marketRule = config.market_rule ?? {}
  const riskPolicies: string[] = config.risk_policies ?? []

  return (
    <div className="card p-4 space-y-3">
      <h3 className="text-sm font-semibold text-gray-700">Config Preview</h3>
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <span className="text-gray-500">Type</span>
          <div className="font-medium">{config.strategy_type ?? 'StaticTopN'}</div>
        </div>
        <div>
          <span className="text-gray-500">Rebalance</span>
          <div className="font-medium">{REBALANCE_LABELS[config.rebalance_frequency ?? '1d'] ?? config.rebalance_frequency}</div>
        </div>
        <div>
          <span className="text-gray-500">Market</span>
          <div className="font-medium">{MARKET_LABELS[marketRule.market ?? 'CN'] ?? 'A-Share'}</div>
        </div>
        <div>
          <span className="text-gray-500">Adj Type</span>
          <div className="font-medium">{ADJ_LABELS[marketRule.adj_type ?? 'forward'] ?? 'Forward'}</div>
        </div>
        <div>
          <span className="text-gray-500">Top N</span>
          <div className="font-medium">{config.top_n ?? 10}</div>
        </div>
        <div>
          <span className="text-gray-500">Sizer</span>
          <div className="font-medium">{config.sizer ?? 'equal_weight'}</div>
        </div>
      </div>

      {factors.length > 0 && (
        <div>
          <span className="text-xs text-gray-500">Factors ({factors.length})</span>
          <div className="flex flex-wrap gap-1 mt-1">
            {factors.slice(0, 8).map(f => (
              <span key={f} className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-[10px] font-mono">{f}</span>
            ))}
            {factors.length > 8 && <span className="text-[10px] text-gray-400">+{factors.length - 8} more</span>}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-gray-500">Max Position</span>
          <div className="font-medium">{((riskLimits.max_position_pct ?? 0.10) * 100).toFixed(0)}%</div>
        </div>
        <div>
          <span className="text-gray-500">Max Leverage</span>
          <div className="font-medium">{riskLimits.max_gross_leverage ?? 1.0}x</div>
        </div>
      </div>

      {riskPolicies.length > 0 && (
        <div>
          <span className="text-xs text-gray-500">Risk Policies</span>
          <div className="flex flex-wrap gap-1 mt-1">
            {riskPolicies.map(p => (
              <span key={p} className="px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded text-[10px]">{p}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

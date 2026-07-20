/**
 * FactorHelpPanel — Displays detailed information about a factor.
 *
 * Shows description, parameters, formula, economic meaning, and use case.
 * Reusable for FactorSelector and IndicatorPicker.
 */
import type { AvailableFactor } from '@/lib/api/factors'

interface FactorHelpPanelProps {
  factor: AvailableFactor | null
  onClose: () => void
}

export function FactorHelpPanel({ factor, onClose }: FactorHelpPanelProps) {
  if (!factor) return null

  return (
    <div className="border rounded-lg p-4 bg-white shadow-lg max-w-md">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-medium text-gray-900">{factor.label_zh}</h3>
          <p className="text-xs text-gray-500 font-mono">{factor.name}</p>
        </div>
        <button
          className="text-gray-400 hover:text-gray-600 text-sm"
          onClick={onClose}
          aria-label="关闭"
        >
          ✕
        </button>
      </div>

      <div className="space-y-3 text-sm">
        {/* Description */}
        <div>
          <div className="text-xs font-medium text-gray-500 mb-1">说明</div>
          <p className="text-gray-700">{factor.description}</p>
        </div>

        {/* Formula */}
        {factor.formula && (
          <div>
            <div className="text-xs font-medium text-gray-500 mb-1">公式</div>
            <code className="block p-2 bg-gray-50 rounded text-xs font-mono text-gray-800 break-all">
              {factor.formula}
            </code>
          </div>
        )}

        {/* Economic Meaning */}
        {factor.economic_meaning && (
          <div>
            <div className="text-xs font-medium text-gray-500 mb-1">经济含义</div>
            <p className="text-gray-700">{factor.economic_meaning}</p>
          </div>
        )}

        {/* Use Case */}
        {factor.use_case && (
          <div>
            <div className="text-xs font-medium text-gray-500 mb-1">应用场景</div>
            <p className="text-gray-700">{factor.use_case}</p>
          </div>
        )}
      </div>
    </div>
  )
}

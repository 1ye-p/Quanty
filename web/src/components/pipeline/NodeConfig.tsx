/**
 * NodeConfig — Side panel for configuring a pipeline node.
 *
 * Shows different config fields depending on nodeType.
 */
import { useState, useEffect } from 'react'
import type { PipelineNodeData } from './PipelineDAG'

// ── Per-type field definitions ───────────────────────────────────────────────

interface FieldDef {
  key: string
  label: string
  type: 'text' | 'number' | 'date' | 'select'
  placeholder?: string
  options?: { value: string; label: string }[]
}

const FIELDS_BY_TYPE: Record<string, FieldDef[]> = {
  data: [
    { key: 'source', label: '数据源', type: 'select', options: [
      { value: 'tdx', label: '通达信' },
      { value: 'tushare', label: 'Tushare' },
      { value: 'akshare', label: 'AKShare' },
    ]},
    { key: 'start_date', label: '开始日期', type: 'date' },
    { key: 'end_date', label: '结束日期', type: 'date' },
  ],
  factor: [
    { key: 'factor_set', label: '因子集', type: 'select', options: [
      { value: 'alpha158', label: 'Alpha158' },
      { value: 'alpha101', label: 'Alpha101' },
      { value: 'gtja191', label: 'GTJA191' },
      { value: 'all', label: '全部因子' },
    ]},
    { key: 'universe', label: '股票池', type: 'select', options: [
      { value: 'hs300', label: '沪深300' },
      { value: 'zz500', label: '中证500' },
      { value: 'zz1000', label: '中证1000' },
      { value: 'all', label: '全市场' },
    ]},
  ],
  model: [
    { key: 'model_name', label: '模型', type: 'select', options: [
      { value: 'lightgbm', label: 'LightGBM' },
      { value: 'xgboost', label: 'XGBoost' },
      { value: 'random_forest', label: '随机森林' },
    ]},
    { key: 'n_folds', label: '交叉验证折数', type: 'number', placeholder: '5' },
  ],
  backtest: [
    { key: 'strategy_type', label: '策略类型', type: 'select', options: [
      { value: 'top_n', label: 'Top-N 选股' },
      { value: 'ml_signal', label: 'ML 信号' },
      { value: 'multi_factor', label: '多因子' },
    ]},
    { key: 'top_n', label: '选股数量', type: 'number', placeholder: '10' },
  ],
  optimize: [
    { key: 'method', label: '优化方法', type: 'select', options: [
      { value: 'mvo', label: '均值-方差 (MVO)' },
      { value: 'risk_parity', label: '风险平价' },
      { value: 'min_variance', label: '最小方差' },
    ]},
    { key: 'max_weight', label: '单股权重上限', type: 'number', placeholder: '0.1' },
  ],
}

// ── Props ───────────────────────────────────────────────────────────────────

export interface NodeConfigProps {
  nodeId: string
  data: PipelineNodeData
  onSave: (nodeId: string, config: Record<string, unknown>) => void
  onClose: () => void
}

export function NodeConfig({ nodeId, data, onSave, onClose }: NodeConfigProps) {
  const fields = FIELDS_BY_TYPE[data.nodeType] ?? []
  const [values, setValues] = useState<Record<string, string>>({})

  // Initialize from existing config
  useEffect(() => {
    const initial: Record<string, string> = {}
    for (const f of fields) {
      const v = data.config?.[f.key]
      initial[f.key] = v != null ? String(v) : ''
    }
    setValues(initial)
  }, [data.config, fields])

  const handleChange = (key: string, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }))
  }

  const handleSave = () => {
    // Convert numeric fields
    const config: Record<string, unknown> = {}
    for (const f of fields) {
      const raw = values[f.key]
      if (raw === '') continue
      config[f.key] = f.type === 'number' ? Number(raw) : raw
    }
    onSave(nodeId, config)
  }

  return (
    <div className="fixed inset-y-0 right-0 w-80 bg-white shadow-xl border-l border-gray-200 z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <h3 className="text-sm font-semibold text-gray-800">
          配置: {data.label}
        </h3>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 text-lg leading-none"
          aria-label="关闭"
        >
          &times;
        </button>
      </div>

      {/* Fields */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {fields.length === 0 ? (
          <p className="text-sm text-gray-400">该节点类型暂无可配置项</p>
        ) : (
          fields.map((f) => (
            <div key={f.key}>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                {f.label}
              </label>
              {f.type === 'select' ? (
                <select
                  value={values[f.key] ?? ''}
                  onChange={(e) => handleChange(f.key, e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">请选择...</option>
                  {f.options?.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              ) : (
                <input
                  type={f.type}
                  value={values[f.key] ?? ''}
                  onChange={(e) => handleChange(f.key, e.target.value)}
                  placeholder={f.placeholder}
                  className="w-full border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              )}
            </div>
          ))
        )}
      </div>

      {/* Actions */}
      <div className="px-4 py-3 border-t border-gray-100 flex gap-2">
        <button
          onClick={onClose}
          className="flex-1 btn-secondary text-sm"
        >
          取消
        </button>
        <button
          onClick={handleSave}
          className="flex-1 btn-primary text-sm"
        >
          保存
        </button>
      </div>
    </div>
  )
}

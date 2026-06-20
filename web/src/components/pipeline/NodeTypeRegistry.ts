/**
 * NodeTypeRegistry — Defines available node types for the PipelineDAG editor.
 *
 * Each node type has a visual style (color, icon), category, and default config.
 * Used by NodePalette for drag-and-drop and by PipelineDAG for rendering.
 */

export interface NodeTypeDef {
  type: string
  label: string
  icon: string
  color: { bg: string; border: string; text: string }
  description: string
  category: 'input' | 'processing' | 'output' | 'utility'
  defaultConfig: Record<string, unknown>
}

export const NODE_TYPES: NodeTypeDef[] = [
  {
    type: 'data_source',
    label: '数据源',
    icon: '📊',
    color: { bg: '#dbeafe', border: '#3b82f6', text: '#1e40af' },
    description: '加载数据',
    category: 'input',
    defaultConfig: { source: 'tdx' },
  },
  {
    type: 'factor_calc',
    label: '因子计算',
    icon: '🔢',
    color: { bg: '#f3e8ff', border: '#a855f7', text: '#7e22ce' },
    description: '计算因子',
    category: 'processing',
    defaultConfig: { factor_set: 'alpha158' },
  },
  {
    type: 'model_train',
    label: '模型训练',
    icon: '🤖',
    color: { bg: '#fef3c7', border: '#f59e0b', text: '#b45309' },
    description: '训练ML模型',
    category: 'processing',
    defaultConfig: { model: 'lightgbm' },
  },
  {
    type: 'backtest',
    label: '回测',
    icon: '📈',
    color: { bg: '#dcfce7', border: '#22c55e', text: '#15803d' },
    description: '运行回测',
    category: 'processing',
    defaultConfig: { engine: 'vector' },
  },
  {
    type: 'optimize',
    label: '组合优化',
    icon: '⚖️',
    color: { bg: '#fee2e2', border: '#ef4444', text: '#b91c1c' },
    description: '组合优化',
    category: 'processing',
    defaultConfig: { method: 'mvo' },
  },
  {
    type: 'merge',
    label: '合并',
    icon: '🔗',
    color: { bg: '#e0f2fe', border: '#0ea5e9', text: '#0369a1' },
    description: '合并多条路径',
    category: 'utility',
    defaultConfig: {},
  },
  {
    type: 'filter',
    label: '过滤',
    icon: '🔍',
    color: { bg: '#fef9c3', border: '#eab308', text: '#a16207' },
    description: '过滤数据',
    category: 'utility',
    defaultConfig: {},
  },
  {
    type: 'custom_script',
    label: '自定义',
    icon: '⚙️',
    color: { bg: '#f1f5f9', border: '#64748b', text: '#334155' },
    description: '自定义脚本',
    category: 'utility',
    defaultConfig: { script: '' },
  },
]

/**
 * Look up a node type definition by its type string.
 */
export function getNodeTypeDef(type: string): NodeTypeDef | undefined {
  return NODE_TYPES.find((t) => t.type === type)
}

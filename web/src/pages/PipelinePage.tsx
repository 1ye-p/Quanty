/**
 * PipelinePage — Enhanced with DAG editor, node configuration, and status display.
 *
 * Uses React Flow for a visual pipeline DAG with default 5-stage pipeline:
 * 数据准备 → 因子计算 → 模型训练 → 回测验证 → 组合优化
 */
import { useState, useMemo, useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { pipelineApi } from '@/lib/api'
import type { Node, Edge } from '@xyflow/react'
import { PipelineDAG, type PipelineNodeData } from '@/components/pipeline/PipelineDAG'
import { NodeConfig } from '@/components/pipeline/NodeConfig'
import { PipelineStatus } from '@/components/pipeline/PipelineStatus'

// ── Default pipeline definition ─────────────────────────────────────────────

const DEFAULT_NODES: Node<PipelineNodeData>[] = [
  {
    id: 'data',
    type: 'dagNode',
    position: { x: 250, y: 0 },
    data: {
      label: '数据准备',
      nodeType: 'data',
      status: 'pending',
      config: { source: 'tdx', start_date: '2024-01-01', end_date: '2025-12-31' },
    },
  },
  {
    id: 'factor',
    type: 'dagNode',
    position: { x: 250, y: 120 },
    data: {
      label: '因子计算',
      nodeType: 'factor',
      status: 'pending',
      config: { factor_set: 'alpha158', universe: 'hs300' },
    },
  },
  {
    id: 'model',
    type: 'dagNode',
    position: { x: 250, y: 240 },
    data: {
      label: '模型训练',
      nodeType: 'model',
      status: 'pending',
      config: { model_name: 'lightgbm', n_folds: 5 },
    },
  },
  {
    id: 'backtest',
    type: 'dagNode',
    position: { x: 250, y: 360 },
    data: {
      label: '回测验证',
      nodeType: 'backtest',
      status: 'pending',
      config: { strategy_type: 'top_n', top_n: 10 },
    },
  },
  {
    id: 'optimize',
    type: 'dagNode',
    position: { x: 250, y: 480 },
    data: {
      label: '组合优化',
      nodeType: 'optimize',
      status: 'pending',
      config: { method: 'mvo', max_weight: 0.1 },
    },
  },
]

const DEFAULT_EDGES: Edge[] = [
  { id: 'e-data-factor', source: 'data', target: 'factor', animated: true, style: { stroke: '#6366f1' } },
  { id: 'e-factor-model', source: 'factor', target: 'model', animated: true, style: { stroke: '#6366f1' } },
  { id: 'e-model-backtest', source: 'model', target: 'backtest', animated: true, style: { stroke: '#6366f1' } },
  { id: 'e-backtest-optimize', source: 'backtest', target: 'optimize', animated: true, style: { stroke: '#6366f1' } },
]

// ── Page component ──────────────────────────────────────────────────────────

export function PipelinePage() {
  const queryClient = useQueryClient()
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [nodeConfigs, setNodeConfigs] = useState<Record<string, Record<string, unknown>>>({})
  const [editable, setEditable] = useState(false)

  // Build nodes with merged configs and live status
  const nodes: Node<PipelineNodeData>[] = useMemo(
    () =>
      DEFAULT_NODES.map((n) => ({
        ...n,
        data: {
          ...n.data,
          config: { ...n.data.config, ...nodeConfigs[n.id] },
        },
      })),
    [nodeConfigs],
  )

  const edges = DEFAULT_EDGES

  // Run pipeline mutation
  const runMutation = useMutation({
    mutationFn: () => pipelineApi.run(),
    onSuccess: () => {
      toast.success('管道已启动')
      queryClient.invalidateQueries({ queryKey: ['pipeline'] })
    },
    onError: (e: Error) => toast.error(`管道启动失败: ${e.message}`),
  })

  // Node click → open config panel
  const handleNodeClick = useCallback((nodeId: string, _data: PipelineNodeData) => {
    setSelectedNodeId(nodeId)
  }, [])

  // Save node config
  const handleSaveConfig = useCallback((nodeId: string, config: Record<string, unknown>) => {
    setNodeConfigs((prev) => ({ ...prev, [nodeId]: config }))
    setSelectedNodeId(null)
    toast.success('节点配置已保存')
  }, [])

  // Selected node data for config panel
  const selectedNode = selectedNodeId
    ? nodes.find((n) => n.id === selectedNodeId) ?? null
    : null

  return (
    <div>
      <h1 className="page-title">自动化回测管道</h1>
      <p className="page-subtitle">
        端到端自动化：数据准备 → 因子计算 → 模型训练 → 回测验证 → 组合优化
      </p>

      {/* Status summary */}
      <div className="mb-4">
        <PipelineStatus />
      </div>

      {/* Toolbar */}
      <div className="card p-4 mb-4">
        <div className="flex items-center justify-between">
          <div className="text-sm font-medium text-gray-700">管道 DAG</div>
          <div className="flex gap-2">
            <button
              onClick={() => setEditable((v) => !v)}
              className={`btn-secondary text-sm ${editable ? 'ring-2 ring-indigo-400' : ''}`}
            >
              {editable ? '退出编辑' : '编辑模式'}
            </button>
            <button
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending}
              className="btn-primary text-sm"
            >
              {runMutation.isPending ? '提交中...' : '运行管道'}
            </button>
          </div>
        </div>
      </div>

      {/* DAG editor */}
      <div className="mb-4">
        <PipelineDAG
          initialNodes={nodes}
          initialEdges={edges}
          onNodeClick={handleNodeClick}
          editable={editable}
        />
      </div>

      {/* Node config side panel */}
      {selectedNode && (
        <NodeConfig
          nodeId={selectedNodeId!}
          data={selectedNode.data}
          onSave={handleSaveConfig}
          onClose={() => setSelectedNodeId(null)}
        />
      )}
    </div>
  )
}

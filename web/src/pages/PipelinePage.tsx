/**
 * PipelinePage — Enhanced with DAG editor, node configuration, and status display.
 *
 * Uses React Flow for a visual pipeline DAG with default 5-stage pipeline:
 * 数据准备 → 因子计算 → 模型训练 → 回测验证 → 组合优化
 */
import { useState, useMemo, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { pipelineApi } from '@/lib/api'
import type { Node, Edge } from '@xyflow/react'
import { PipelineDAG, type PipelineNodeData } from '@/components/pipeline/PipelineDAG'
import { NodeConfig } from '@/components/pipeline/NodeConfig'
import { PipelineStatus } from '@/components/pipeline/PipelineStatus'
import { ExecutionHistory } from '@/components/pipeline/ExecutionHistory'
import { RunDialog } from '@/components/pipeline/RunDialog'

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

// ── Tab definitions ─────────────────────────────────────────────────────────

const tabs = [
  { id: 'dag', label: 'DAG 编辑' },
  { id: 'history', label: '执行历史' },
] as const

type PipelineTab = typeof tabs[number]['id']

// ── Page component ──────────────────────────────────────────────────────────

export function PipelinePage() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [nodeConfigs, setNodeConfigs] = useState<Record<string, Record<string, unknown>>>({})
  const [editable, setEditable] = useState(false)
  const [activeTab, setActiveTab] = useState<PipelineTab>('dag')
  const [showRunDialog, setShowRunDialog] = useState(false)

  // Poll pipeline status to drive DAG node colors
  const { data: pipelineStatus } = useQuery({
    queryKey: ['pipeline', 'status'],
    queryFn: () => pipelineApi.status(),
    refetchInterval: 10_000,
  })

  // Build nodes with merged configs and live status
  const nodes: Node<PipelineNodeData>[] = useMemo(() => {
    const stageStatus = (pipelineStatus as Record<string, unknown>)?.stages as Record<string, { status?: string }> | undefined
    return DEFAULT_NODES.map((n) => {
      const liveStatus = stageStatus?.[n.id]?.status
      return {
        ...n,
        data: {
          ...n.data,
          status: (liveStatus as PipelineNodeData['status']) ?? n.data.status,
          config: { ...n.data.config, ...nodeConfigs[n.id] },
        },
      }
    })
  }, [nodeConfigs, pipelineStatus])

  const edges = DEFAULT_EDGES

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
  const selectedNode = selectedNodeId ? nodes.find((n) => n.id === selectedNodeId) : undefined

  return (
    <div>
      <h1 className="page-title">自动化回测管道</h1>
      <p className="page-subtitle">
        端到端自动化：数据准备 → 因子计算 → 模型训练 → 回测验证 → 组合优化
      </p>

      {/* Tab navigation */}
      <div className="flex gap-1 border-b mb-6">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'dag' && (
        <>
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
                  onClick={() => setShowRunDialog(true)}
                  className="btn-primary text-sm"
                  title="管道在后台异步运行，可重复触发"
                >
                  运行管道
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
              nodeId={selectedNode.id}
              data={selectedNode.data}
              onSave={handleSaveConfig}
              onClose={() => setSelectedNodeId(null)}
            />
          )}
        </>
      )}

      {activeTab === 'history' && <ExecutionHistory />}

      {/* Run dialog */}
      {showRunDialog && (
        <RunDialog open={showRunDialog} onClose={() => setShowRunDialog(false)} initialParams={nodeConfigs} />
      )}
    </div>
  )
}

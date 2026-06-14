/**
 * PipelineDAG — Visual DAG editor for pipeline configuration using React Flow.
 *
 * Color-codes nodes by type and supports click-to-configure and edit mode
 * for adding connections.
 */
import { useCallback, useEffect, useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeTypes,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type NodeProps,
  type ColorMode,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

// ── Node type → color mapping ───────────────────────────────────────────────

const TYPE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  data: { bg: '#dbeafe', border: '#3b82f6', text: '#1e40af' },
  factor: { bg: '#f3e8ff', border: '#a855f7', text: '#7e22ce' },
  model: { bg: '#fef3c7', border: '#f59e0b', text: '#b45309' },
  backtest: { bg: '#dcfce7', border: '#22c55e', text: '#15803d' },
  optimize: { bg: '#fee2e2', border: '#ef4444', text: '#b91c1c' },
}

const STATUS_ICON: Record<string, string> = {
  success: '✅',
  running: '⏳',
  error: '❌',
  pending: '⚪',
  idle: '⚪',
}

// ── Custom DAG node ─────────────────────────────────────────────────────────

export interface PipelineNodeData {
  label: string
  nodeType: string // data | factor | model | backtest | optimize
  status?: string
  config?: Record<string, unknown>
  [key: string]: unknown
}

function DAGNode({ data }: NodeProps<Node<PipelineNodeData>>) {
  const { label, nodeType, status } = data
  const colors = TYPE_COLORS[nodeType] ?? TYPE_COLORS.data
  const icon = STATUS_ICON[status ?? 'pending'] ?? STATUS_ICON.pending

  return (
    <div
      className="px-4 py-3 rounded-lg shadow-sm min-w-[140px] text-center cursor-pointer"
      style={{
        backgroundColor: colors.bg,
        border: `2px solid ${colors.border}`,
        color: colors.text,
      }}
    >
      <Handle type="target" position={Position.Top} className="!bg-gray-400" />
      <div className="text-base mb-1">{icon}</div>
      <div className="text-sm font-semibold leading-tight">{label}</div>
      <Handle type="source" position={Position.Bottom} className="!bg-gray-400" />
    </div>
  )
}

const nodeTypes: NodeTypes = {
  dagNode: DAGNode,
}

// ── Props ───────────────────────────────────────────────────────────────────

export interface PipelineDAGProps {
  initialNodes: Node<PipelineNodeData>[]
  initialEdges: Edge[]
  onNodeClick?: (nodeId: string, data: PipelineNodeData) => void
  editable?: boolean
  onEdgesChange?: (edges: Edge[]) => void
}

export function PipelineDAG({
  initialNodes,
  initialEdges,
  onNodeClick,
  editable = false,
  onEdgesChange: onEdgesChangeProp,
}: PipelineDAGProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChangeInternal] = useEdgesState(initialEdges)

  // Sync when initial props change (e.g. status updates)
  useEffect(() => {
    setNodes(initialNodes)
  }, [initialNodes, setNodes])

  useEffect(() => {
    setEdges(initialEdges)
  }, [initialEdges, setEdges])

  const handleEdgesChange: OnEdgesChange = useCallback(
    (changes) => {
      onEdgesChangeInternal(changes)
    },
    [onEdgesChangeInternal],
  )

  const handleConnect: OnConnect = useCallback(
    (connection: Connection) => {
      if (!editable) return
      setEdges((eds) => {
        const updated = addEdge({ ...connection, animated: true, style: { stroke: '#6366f1' } }, eds)
        onEdgesChangeProp?.(updated)
        return updated
      })
    },
    [editable, setEdges, onEdgesChangeProp],
  )

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node<PipelineNodeData>) => {
      onNodeClick?.(node.id, node.data)
    },
    [onNodeClick],
  )

  return (
    <div className="w-full h-[480px] rounded-lg border border-gray-200 overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange as OnNodesChange}
        onEdgesChange={handleEdgesChange}
        onConnect={handleConnect}
        onNodeClick={handleNodeClick as any}
        nodeTypes={nodeTypes}
        fitView
        colorMode={'light' as ColorMode}
        nodesDraggable={editable}
        nodesConnectable={editable}
        elementsSelectable={editable}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} />
        <Controls position="bottom-left" />
        <MiniMap
          nodeColor={(n) => {
            const t = (n.data as PipelineNodeData)?.nodeType ?? 'data'
            return TYPE_COLORS[t]?.border ?? '#94a3b8'
          }}
          maskColor="rgba(0,0,0,0.08)"
          position="bottom-right"
        />
      </ReactFlow>
    </div>
  )
}

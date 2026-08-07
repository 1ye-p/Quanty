/**
 * PipelineDAG — Visual DAG editor for pipeline configuration using React Flow.
 *
 * Color-codes nodes by type and supports click-to-configure, edit mode
 * for connections, drag-and-drop to add nodes, and keyboard deletion.
 */
import { useCallback, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
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
  useReactFlow,
  addEdge,
  type Connection,
  type NodeProps,
  type ColorMode,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { getNodeTypeDef } from './NodeTypeRegistry'

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
  const { t } = useTranslation()
  const { label, nodeType, status } = data
  const typeDef = getNodeTypeDef(nodeType)
  const colors = typeDef ? typeDef.color : TYPE_COLORS.data
  const icon = STATUS_ICON[status ?? 'pending'] ?? STATUS_ICON.pending
  const displayLabel = nodeType
    ? t(`component.pipeline.node_label.${nodeType}`, { defaultValue: label })
    : label

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
      <div className="text-sm font-semibold leading-tight">{displayLabel}</div>
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
  onNodesChange?: OnNodesChange<Node<PipelineNodeData>>
}

export function PipelineDAG({
  initialNodes,
  initialEdges,
  onNodeClick,
  editable = false,
  onEdgesChange: onEdgesChangeProp,
  onNodesChange: onNodesChangeProp,
}: PipelineDAGProps) {
  const { screenToFlowPosition } = useReactFlow()
  const [nodes, setNodes, onNodesChangeInternal] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChangeInternal] = useEdgesState(initialEdges)

  // Sync when initial props change (e.g. status updates)
  useEffect(() => {
    setNodes(initialNodes)
  }, [initialNodes, setNodes])

  useEffect(() => {
    setEdges(initialEdges)
  }, [initialEdges, setEdges])

  // Propagate node changes to parent
  const handleNodesChange: OnNodesChange<Node<PipelineNodeData>> = useCallback(
    (changes) => {
      onNodesChangeInternal(changes)
      onNodesChangeProp?.(changes)
    },
    [onNodesChangeInternal, onNodesChangeProp],
  )

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

  // ── Drag-and-drop: add nodes from palette ──────────────────────────────

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      if (!editable) return

      const type = event.dataTransfer.getData('application/reactflow')
      if (!type) return

      const nodeDef = getNodeTypeDef(type)
      if (!nodeDef) return

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      })

      const newNode: Node<PipelineNodeData> = {
        id: `${type}_${Date.now()}`,
        type: 'dagNode',
        position,
        data: {
          label: nodeDef.label,
          nodeType: type,
          status: 'pending',
          config: { ...nodeDef.defaultConfig },
        },
      }

      setNodes((nds) => [...nds, newNode])
    },
    [editable, screenToFlowPosition, setNodes],
  )

  // ── Keyboard: delete selected nodes/edges ──────────────────────────────

  useEffect(() => {
    if (!editable) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        // Create remove changes for selected nodes/edges and propagate to parent
        setNodes((nds) => {
          const selected = nds.filter((n) => n.selected)
          if (selected.length > 0) {
            const changes = selected.map((n) => ({ id: n.id, type: 'remove' as const }))
            onNodesChangeProp?.(changes as Parameters<NonNullable<typeof onNodesChangeProp>>[0])
          }
          return nds.filter((n) => !n.selected)
        })
        setEdges((eds) => {
          const selected = eds.filter((ed) => ed.selected)
          if (selected.length > 0) {
            const changes = selected.map((ed) => ({ id: ed.id, type: 'remove' as const }))
            onEdgesChangeProp?.(changes as Parameters<NonNullable<typeof onEdgesChangeProp>>[0])
          }
          return eds.filter((ed) => !ed.selected)
        })
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [editable, setNodes, setEdges, onNodesChangeProp, onEdgesChangeProp])

  return (
    <div className="w-full h-[480px] rounded-lg border border-gray-200 overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={handleNodesChange as OnNodesChange}
        onEdgesChange={handleEdgesChange}
        onConnect={handleConnect}
        onNodeClick={handleNodeClick as any}
        onDragOver={onDragOver}
        onDrop={onDrop}
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

/**
 * NodePalette — Sidebar palette for dragging node types onto the PipelineDAG canvas.
 *
 * Each item is draggable; on drop the ReactFlow canvas receives the node type
 * via `dataTransfer.setData('application/reactflow', nodeType)`.
 */
import { useTranslation } from 'react-i18next'
import { NODE_TYPES } from './NodeTypeRegistry'

export function NodePalette() {
  const { t } = useTranslation()
  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData('application/reactflow', nodeType)
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <div className="w-48 bg-white border-r p-3 space-y-2">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">{t('component.pipeline.node_type')}</h3>
      {NODE_TYPES.map((nt) => (
        <div
          key={nt.type}
          className="flex items-center gap-2 p-2 rounded cursor-grab hover:bg-gray-50 border"
          style={{ borderColor: nt.color.border, backgroundColor: nt.color.bg }}
          onDragStart={(e) => onDragStart(e, nt.type)}
          draggable
        >
          <span>{nt.icon}</span>
          <span className="text-xs font-medium" style={{ color: nt.color.text }}>
            {t(`component.pipeline.node_label.${nt.type}`, { defaultValue: nt.label })}
          </span>
        </div>
      ))}
    </div>
  )
}

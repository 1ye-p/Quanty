/**
 * Model display card.
 * Shows model name, description, engine badge, and selected state.
 */

interface ModelCardProps {
  name: string
  displayName: string
  engine: string
  description: string
  selected?: boolean
  onClick?: () => void
}

export function ModelCard({ name, displayName, engine, description, selected, onClick }: ModelCardProps) {
  return (
    <div
      onClick={onClick}
      className={`p-3 rounded-lg cursor-pointer transition-all border-2 ${
        selected ? 'border-blue-500 bg-blue-50' : 'border-transparent bg-gray-50 hover:bg-gray-100'
      }`}
    >
      <div className="font-medium text-gray-900 text-sm">{displayName}</div>
      <div className="text-xs text-gray-500 mt-1 line-clamp-2">{description}</div>
      <div className="flex items-center gap-2 mt-2">
        <span className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-[10px]">{name}</span>
        {engine === 'qlib' && (
          <span className="px-1.5 py-0.5 bg-purple-50 text-purple-700 rounded text-[10px]">qlib</span>
        )}
      </div>
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import { knowledgeApi, type KnowledgeDoc } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

interface DocumentListProps {
  tag: string | null
  selectedId: string | null
  onSelect: (doc: KnowledgeDoc) => void
}

function getFileIcon(logicalType: string, sourceName: string): string {
  const lower = (sourceName || '').toLowerCase()
  if (logicalType === 'pdf' || lower.endsWith('.pdf')) return '📕'
  if (logicalType === 'docx' || lower.endsWith('.doc') || lower.endsWith('.docx')) return '📘'
  if (lower.endsWith('.md') || logicalType === 'markdown') return '📗'
  if (lower.endsWith('.py') || logicalType === 'python') return '🐍'
  if (lower.endsWith('.ipynb') || logicalType === 'notebook') return '📓'
  return '📄'
}

export function DocumentList({ tag, selectedId, onSelect }: DocumentListProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.knowledge.list(tag ?? undefined),
    queryFn: () => knowledgeApi.list({ tag: tag ?? undefined }),
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="card animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
            <div className="h-3 bg-gray-200 rounded w-1/2" />
          </div>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-red-500 text-sm p-4">
        加载失败：{error instanceof Error ? error.message : String(error)}
      </div>
    )
  }

  const items = data?.items ?? []
  if (items.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400 text-sm">
        暂无文档
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {items.map(doc => (
        <div
          key={doc.doc_id}
          onClick={() => onSelect(doc)}
          className={`p-3 rounded-lg cursor-pointer transition-colors ${
            selectedId === doc.doc_id
              ? 'bg-brand-50 border border-brand-200'
              : 'hover:bg-gray-50 border border-transparent'
          }`}
        >
          <div className="flex items-start gap-2">
            <span className="text-lg flex-shrink-0">
              {getFileIcon(doc.logical_type, doc.source_name)}
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-gray-900 truncate">
                {doc.title || <em className="text-gray-400">无标题</em>}
              </div>
              <div className="flex items-center gap-2 mt-1">
                {doc.tags?.map(tag => (
                  <span
                    key={tag}
                    className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500"
                  >
                    {tag}
                  </span>
                ))}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {doc.ingested_at?.slice(0, 10) ?? ''}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

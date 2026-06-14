import { useQuery } from '@tanstack/react-query'
import { knowledgeApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

interface DocumentTagsProps {
  selectedTag: string | null
  onTagSelect: (tag: string | null) => void
}

export function DocumentTags({ selectedTag, onTagSelect }: DocumentTagsProps) {
  const { data, isLoading } = useQuery({
    queryKey: queryKeys.knowledge.tags(),
    queryFn: () => knowledgeApi.getTags(),
  })

  if (isLoading) {
    return (
      <div className="flex gap-2 animate-pulse">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-8 w-16 bg-gray-200 rounded-full" />
        ))}
      </div>
    )
  }

  const tags = data?.tags ?? []
  if (tags.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2">
      <button
        onClick={() => onTagSelect(null)}
        className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
          selectedTag === null
            ? 'bg-brand-600 text-white'
            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
        }`}
      >
        全部
      </button>
      {tags.map(tag => (
        <button
          key={tag}
          onClick={() => onTagSelect(tag)}
          className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
            selectedTag === tag
              ? 'bg-brand-600 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          {tag}
        </button>
      ))}
    </div>
  )
}

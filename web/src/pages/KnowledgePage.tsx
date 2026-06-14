import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { knowledgeApi, type KnowledgeDoc, type SearchHit } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { toast } from 'sonner'
import { DocumentUpload } from '@/components/knowledge/DocumentUpload'
import { DocumentPreview } from '@/components/knowledge/DocumentPreview'
import { DocumentTags } from '@/components/knowledge/DocumentTags'
import { DocumentList } from '@/components/knowledge/DocumentList'

export function KnowledgePage() {
  const [showUpload, setShowUpload] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [submitted, setSubmitted] = useState('')
  const [selectedTag, setSelectedTag] = useState<string | null>(null)
  const [selectedDoc, setSelectedDoc] = useState<KnowledgeDoc | null>(null)
  const qc = useQueryClient()

  // Search
  const { data: results, isFetching: searching } = useQuery({
    queryKey: queryKeys.knowledge.search(submitted),
    queryFn: () => knowledgeApi.search(submitted),
    enabled: submitted.length > 0,
  })

  // Delete
  const deleteMutation = useMutation({
    mutationFn: (id: string) => knowledgeApi.delete(id),
    onSuccess: () => {
      toast.success('文档已删除')
      setSelectedDoc(null)
      qc.invalidateQueries({ queryKey: queryKeys.knowledge.all })
    },
    onError: (err: Error) => toast.error(`删除失败：${err.message}`),
  })

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    setSubmitted(searchText.trim())
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 mb-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="page-title">知识库</h1>
            <p className="page-subtitle">研报、策略文档、笔记管理与语义检索</p>
          </div>
          <button
            className="btn-primary"
            onClick={() => setShowUpload(prev => !prev)}
          >
            {showUpload ? '收起' : '上传文档'}
          </button>
        </div>

        {/* Search */}
        <form onSubmit={handleSearch} className="flex gap-2 mb-4">
          <input
            type="text"
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            placeholder="搜索文档…（语义 + 关键词混合检索）"
            className="input flex-1"
          />
          <button type="submit" className="btn-primary">搜索</button>
        </form>

        {/* Upload (conditional) */}
        {showUpload && (
          <div className="mb-4">
            <DocumentUpload onSuccess={() => setShowUpload(false)} />
          </div>
        )}

        {/* Search results */}
        {submitted && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-600 mb-3">
              {searching ? '搜索中…' : `"${submitted}" 的结果（${results?.total_found ?? 0} 条）`}
            </h3>
            <div className="space-y-2">
              {results?.hits.map((hit: SearchHit) => (
                <div
                  key={hit.doc_id}
                  className="card cursor-pointer hover:bg-gray-50"
                  onClick={() => {
                    setSelectedDoc({
                      doc_id: hit.doc_id,
                      title: hit.title,
                      source_name: hit.source_name,
                      logical_type: hit.logical_type,
                      language: '',
                      ingested_at: '',
                    })
                    setSubmitted('')
                    setSearchText('')
                  }}
                >
                  <div className="font-medium text-gray-900">{hit.title || '无标题'}</div>
                  <div className="text-xs text-gray-400 mt-1">
                    {hit.source_name} · {hit.logical_type} · 相关度 {hit.score.toFixed(3)}
                  </div>
                  {hit.headline && (
                    <div className="mt-2 text-sm text-gray-600 italic">{hit.headline}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tags filter */}
        <DocumentTags selectedTag={selectedTag} onTagSelect={setSelectedTag} />
      </div>

      {/* Main content: 3-column layout */}
      <div className="flex-1 grid grid-cols-3 gap-4 min-h-0">
        {/* Left: Document list */}
        <div className="col-span-1 card overflow-auto p-3">
          <DocumentList
            tag={selectedTag}
            selectedId={selectedDoc?.doc_id ?? null}
            onSelect={setSelectedDoc}
          />
        </div>

        {/* Right: Preview (2 cols) */}
        <div className="col-span-2 flex flex-col min-h-0">
          {/* Action bar */}
          {selectedDoc && (
            <div className="flex items-center justify-between mb-2 px-1">
              <div className="text-sm font-medium text-gray-700 truncate">
                {selectedDoc.title || selectedDoc.source_name}
              </div>
              <button
                className="text-sm text-red-500 hover:text-red-700 transition-colors"
                disabled={deleteMutation.isPending}
                onClick={() => {
                  if (confirm('确定删除该文档？')) {
                    deleteMutation.mutate(selectedDoc.doc_id)
                  }
                }}
              >
                {deleteMutation.isPending ? '删除中…' : '删除'}
              </button>
            </div>
          )}
          {/* Preview */}
          <div className="flex-1 min-h-0">
            <DocumentPreview
              docId={selectedDoc?.doc_id ?? null}
              fileName={selectedDoc?.source_name}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

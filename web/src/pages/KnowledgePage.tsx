import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { knowledgeApi, type KnowledgeDoc, type SearchHit, type QAResponse } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { toast } from 'sonner'
import { DocumentUpload } from '@/components/knowledge/DocumentUpload'
import { DocumentPreview } from '@/components/knowledge/DocumentPreview'
import { DocumentTags } from '@/components/knowledge/DocumentTags'
import { DocumentList } from '@/components/knowledge/DocumentList'

// ── Tab type ─────────────────────────────────────────────────────────────────
type TabKey = 'search' | 'qa'

// ── Q&A history entry ────────────────────────────────────────────────────────
interface QAEntry {
  id: string
  question: string
  answer: string
  sources: QAResponse['sources']
  model: string
  timestamp: number
}

// ── Q&A Tab Component ────────────────────────────────────────────────────────
function QATab() {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<QAEntry[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const qaMutation = useMutation({
    mutationFn: (q: string) => knowledgeApi.qa({ question: q }),
    onSuccess: (data, q) => {
      setHistory(prev => [
        ...prev,
        {
          id: crypto.randomUUID(),
          question: q,
          answer: data.answer,
          sources: data.sources,
          model: data.model,
          timestamp: Date.now(),
        },
      ])
      setQuestion('')
    },
    onError: (err: Error) => {
      toast.error(err.message || '问答失败，请重试')
    },
  })

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [history, qaMutation.isPending])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q || qaMutation.isPending) return
    qaMutation.mutate(q)
  }

  return (
    <div className="flex flex-col h-full">
      {/* History area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-4 pb-4">
        {history.length === 0 && !qaMutation.isPending && (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <svg
              className="w-12 h-12 mb-3 text-gray-300"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
            <p className="text-sm">向知识库提问，获取基于文档的智能回答</p>
            <p className="text-xs mt-1 text-gray-300">支持语义检索 + LLM 生成</p>
          </div>
        )}

        {history.map((entry) => (
          <div key={entry.id} className="space-y-3">
            {/* Question */}
            <div className="flex justify-end">
              <div className="bg-indigo-500 text-white rounded-2xl rounded-br-md px-4 py-2.5 max-w-[80%] text-sm">
                {entry.question}
              </div>
            </div>

            {/* Answer */}
            <div className="flex justify-start">
              <div className="bg-white rounded-2xl rounded-bl-md shadow-sm border p-4 max-w-[85%]">
                <div className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                  {entry.answer}
                </div>

                {/* Sources / Citations */}
                {entry.sources.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-100">
                    <p className="text-xs font-medium text-gray-500 mb-2">
                      参考来源（{entry.sources.length} 条）
                    </p>
                    <div className="space-y-1.5">
                      {entry.sources.map((src: QAResponse['sources'][number], i: number) => (
                        <div key={src.doc_id} className="flex items-start gap-2">
                          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-indigo-100 text-indigo-600 text-[10px] font-semibold flex-shrink-0 mt-0.5">
                            {i + 1}
                          </span>
                          <div className="min-w-0">
                            <p className="text-xs text-gray-600 line-clamp-2">
                              {src.snippet}
                            </p>
                            <p className="text-[10px] text-gray-400 mt-0.5">
                              文档 {src.doc_id.slice(0, 8)}... 相关度 {src.score.toFixed(3)}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="mt-2 text-[10px] text-gray-300 text-right">
                  {entry.model}
                </div>
              </div>
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {qaMutation.isPending && (
          <div className="flex justify-start">
            <div className="bg-white rounded-2xl rounded-bl-md shadow-sm border px-4 py-3">
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                思考中...
              </div>
            </div>
          </div>
        )}

        {/* Error state */}
        {qaMutation.isError && (
          <div className="flex justify-start">
            <div className="bg-red-50 rounded-2xl rounded-bl-md border border-red-200 px-4 py-3">
              <p className="text-sm text-red-600">
                {qaMutation.error.message.includes('empty')
                  ? '知识库为空，请先上传文档'
                  : `问答失败：${qaMutation.error.message}`}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 pt-3 border-t border-gray-200">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="输入问题，例如：如何构建多因子策略？"
            className="input flex-1"
            disabled={qaMutation.isPending}
          />
          <button
            type="submit"
            className="btn-primary"
            disabled={!question.trim() || qaMutation.isPending}
          >
            {qaMutation.isPending ? '发送中...' : '提问'}
          </button>
        </form>
      </div>
    </div>
  )
}

// ── Search Tab (existing logic extracted) ────────────────────────────────────
function SearchTab({
  selectedDoc,
  setSelectedDoc,
}: {
  selectedDoc: KnowledgeDoc | null
  setSelectedDoc: (doc: KnowledgeDoc | null) => void
}) {
  const [showUpload, setShowUpload] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [submitted, setSubmitted] = useState('')
  const [selectedTag, setSelectedTag] = useState<string | null>(null)
  const qc = useQueryClient()

  const { data: results, isFetching: searching } = useQuery({
    queryKey: queryKeys.knowledge.search(submitted),
    queryFn: () => knowledgeApi.search(submitted),
    enabled: submitted.length > 0,
  })

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
    <>
      {/* Search + Upload header */}
      <div className="flex-shrink-0 mb-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-sm text-gray-500">研报、策略文档、笔记管理与语义检索</p>
          </div>
          <button
            className="btn-primary"
            onClick={() => setShowUpload((prev) => !prev)}
          >
            {showUpload ? '收起' : '上传文档'}
          </button>
        </div>

        {/* Search */}
        <form onSubmit={handleSearch} className="flex gap-2 mb-4">
          <input
            type="text"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
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
    </>
  )
}

// ── Main Page ────────────────────────────────────────────────────────────────
export function KnowledgePage() {
  const [activeTab, setActiveTab] = useState<TabKey>('search')
  const [selectedDoc, setSelectedDoc] = useState<KnowledgeDoc | null>(null)

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'search', label: '搜索' },
    { key: 'qa', label: '问答' },
  ]

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between mb-4">
        <h1 className="page-title">知识库</h1>
        {/* Tab navigation */}
        <div className="flex items-center bg-gray-100 rounded-lg p-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
                activeTab === tab.key
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 min-h-0 flex flex-col">
        {activeTab === 'search' ? (
          <SearchTab selectedDoc={selectedDoc} setSelectedDoc={setSelectedDoc} />
        ) : (
          <QATab />
        )}
      </div>
    </div>
  )
}

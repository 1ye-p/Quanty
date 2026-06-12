import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { knowledgeApi, type SearchHit } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { toast } from 'sonner'
import { DataState } from '@/components/ui/DataState'

export function KnowledgePage() {
  const [searchText, setSearchText] = useState('')
  const [submitted, setSubmitted] = useState('')
  const [ingestUri, setIngestUri] = useState('')
  const [ingestTitle, setIngestTitle] = useState('')
  const [ingestSource, setIngestSource] = useState('')
  const qc = useQueryClient()

  const ingestMutation = useMutation({
    mutationFn: () => knowledgeApi.ingest({
      uri: ingestUri,
      title: ingestTitle || undefined,
      source_name: ingestSource || undefined,
    }),
    onSuccess: () => {
      toast.success('文档已导入并索引')
      qc.invalidateQueries({ queryKey: queryKeys.knowledge.list() })
      setIngestUri('')
      setIngestTitle('')
      setIngestSource('')
    },
    onError: (err: Error) => toast.error(`导入失败：${err.message}`),
  })

  const { data: docs, isLoading } = useQuery({
    queryKey: queryKeys.knowledge.list(),
    queryFn: () => knowledgeApi.list(),
  })

  const { data: results, isFetching: searching } = useQuery({
    queryKey: queryKeys.knowledge.search(submitted),
    queryFn: () => knowledgeApi.search(submitted),
    enabled: submitted.length > 0,
  })

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    setSubmitted(searchText.trim())
  }

  return (
    <div>
      <h1 className="page-title">知识库</h1>
      <p className="page-subtitle">研报、策略文档、笔记管理与语义检索</p>

      <form onSubmit={handleSearch} className="flex gap-2 mb-6">
        <input
          type="text"
          value={searchText}
          onChange={e => setSearchText(e.target.value)}
          placeholder="搜索文档…（语义 + 关键词混合检索）"
          className="input flex-1"
        />
        <button type="submit" className="btn-primary">搜索</button>
      </form>

      {/* Ingest section */}
      <div className="card mb-6">
        <h2 className="font-semibold text-gray-800 mb-3">导入知识文档</h2>
        <div className="grid grid-cols-3 gap-3 mb-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">文档路径/URL</label>
            <input type="text" className="input w-full" placeholder="/path/to/file.pdf 或 https://..."
              value={ingestUri} onChange={e => setIngestUri(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">标题（可选）</label>
            <input type="text" className="input w-full" placeholder="文档标题"
              value={ingestTitle} onChange={e => setIngestTitle(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">来源标签</label>
            <input type="text" className="input w-full" placeholder="研报/策略/笔记"
              value={ingestSource} onChange={e => setIngestSource(e.target.value)} />
          </div>
        </div>
        <div className="flex justify-end">
          <button className="btn-primary" disabled={!ingestUri || ingestMutation.isPending}
            onClick={() => ingestMutation.mutate()}>
            {ingestMutation.isPending ? '导入中…' : '导入并索引'}
          </button>
        </div>
      </div>

      {submitted && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-600 mb-3">
            {searching ? '搜索中…' : `"${submitted}" 的结果（${results?.total_found ?? 0} 条）`}
          </h3>
          <div className="space-y-3">
            {results?.hits.map((hit: SearchHit) => (
              <div key={hit.doc_id} className="card">
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

      <h2 className="text-lg font-semibold text-gray-800 mb-3">所有文档（{docs?.total ?? 0}）</h2>
      <DataState isLoading={isLoading} isEmpty={!isLoading && !docs?.items.length} emptyText="暂无文档，请先导入">
        <div className="card p-0 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                {['标题', '来源', '类型', '语言', '入库时间'].map(h => (
                  <th key={h} className="table-th">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {docs?.items.map(d => (
                <tr key={d.doc_id} className="table-row">
                  <td className="table-td font-medium">{d.title || <em className="text-gray-400">无标题</em>}</td>
                  <td className="table-td text-gray-500">{d.source_name || '—'}</td>
                  <td className="table-td">{d.logical_type}</td>
                  <td className="table-td">{d.language}</td>
                  <td className="table-td text-gray-400 text-xs">{d.ingested_at?.slice(0, 16) ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </DataState>
    </div>
  )
}

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { knowledgeApi, type SearchHit } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

export function KnowledgePage() {
  const [searchText, setSearchText] = useState('')
  const [submitted, setSubmitted] = useState('')

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
      {isLoading && <p className="text-gray-400">Loading…</p>}
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
            {!docs?.items.length && (
              <tr><td colSpan={5} className="table-td text-center text-gray-400 py-8">暂无文档，请先导入</td></tr>
            )}
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
    </div>
  )
}

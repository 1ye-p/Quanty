import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { newsApi, type NewsEvent } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'

function NewsDetail({ eventId }: { eventId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: extendedQueryKeys.news.detail(eventId),
    queryFn: () => newsApi.get(eventId),
  })

  if (isLoading) return <div className="text-gray-400 text-sm">加载详情中...</div>
  if (!data) return <div className="text-red-500 text-sm">加载失败</div>

  return (
    <div className="space-y-2">
      {data.body && (
        <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{data.body}</div>
      )}
      {!data.body && (
        <div className="text-xs text-gray-400">暂无正文内容</div>
      )}
    </div>
  )
}

function SentimentDot({ score }: { score: number | null }) {
  if (score === null) return <span className="w-2 h-2 rounded-full bg-gray-300 inline-block" />
  if (score > 0.2) return <span className="w-2 h-2 rounded-full bg-green-400 inline-block" title={`情绪: ${score.toFixed(2)}`} />
  if (score < -0.2) return <span className="w-2 h-2 rounded-full bg-red-400 inline-block" title={`情绪: ${score.toFixed(2)}`} />
  return <span className="w-2 h-2 rounded-full bg-gray-400 inline-block" title={`情绪: ${score.toFixed(2)}`} />
}

export function NewsPage() {
  const [source, setSource] = useState('')
  const [eventType, setEventType] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)

  const params: Record<string, string> = {}
  if (source) params.source = source
  if (eventType) params.event_type = eventType

  const { data, isLoading } = useQuery({
    queryKey: extendedQueryKeys.news.list(params),
    queryFn: () => newsApi.list(params),
  })

  const { data: stats } = useQuery({
    queryKey: extendedQueryKeys.news.stats(),
    queryFn: newsApi.stats,
  })

  const sources = Object.keys(stats?.source_counts ?? {})
  const eventTypes = Object.keys(stats?.event_type_counts ?? {})

  return (
    <div>
      <h1 className="page-title">消息面</h1>
      <p className="page-subtitle">新闻事件浏览 · 情绪过滤 · 资产关联</p>

      {/* Stats */}
      {stats && (
        <div className="flex gap-4 mb-6 flex-wrap">
          <div className="card py-3 px-5">
            <div className="text-2xl font-bold text-brand-600">{stats.total_events.toLocaleString()}</div>
            <div className="text-xs text-gray-500">条新闻事件</div>
          </div>
          {stats.avg_sentiment !== null && (
            <div className="card py-3 px-5">
              <div className={`text-2xl font-bold ${stats.avg_sentiment > 0 ? 'text-green-600' : 'text-red-600'}`}>
                {stats.avg_sentiment.toFixed(3)}
              </div>
              <div className="text-xs text-gray-500">平均情绪分</div>
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 mb-4">
        <select className="input max-w-[160px]" value={source} onChange={e => setSource(e.target.value)}>
          <option value="">全部来源</option>
          {sources.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="input max-w-[160px]" value={eventType} onChange={e => setEventType(e.target.value)}>
          <option value="">全部类型</option>
          {eventTypes.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {isLoading && <p className="text-gray-400">Loading…</p>}

      <div className="space-y-3">
        {!data?.items.length && !isLoading && (
          <div className="text-center text-gray-400 py-12">暂无新闻数据，请先运行 newsflow 接入</div>
        )}
        {data?.items.map((item: NewsEvent) => (
          <div key={item.event_id} className="card cursor-pointer hover:shadow-md transition-shadow"
            onClick={() => setExpanded(expanded === item.event_id ? null : item.event_id)}>
            <div className="flex items-start gap-3">
              <SentimentDot score={item.sentiment_score} />
              <div className="flex-1 min-w-0">
                <div className="font-medium text-gray-900 leading-snug">{item.headline}</div>
                <div className="flex gap-3 mt-1 text-xs text-gray-400">
                  <span>{item.source}</span>
                  <span>{item.event_type}</span>
                  <span>{item.published_at?.slice(0, 16) ?? '—'}</span>
                </div>
                {item.asset_ids_mentioned.length > 0 && (
                  <div className="flex gap-1 mt-2 flex-wrap">
                    {item.asset_ids_mentioned.map(a => (
                      <span key={a} className="badge bg-indigo-50 text-indigo-700 text-xs">{a}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
            {expanded === item.event_id && (
              <div className="mt-3 pt-3 border-t border-gray-100">
                <NewsDetail eventId={item.event_id} />
                <div className="mt-2 text-xs text-gray-400">
                  event_id: <code className="bg-gray-100 px-1 rounded">{item.event_id}</code>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

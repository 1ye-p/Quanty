import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { newsApi, tradingApi, type NewsEvent } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine,
  ResponsiveContainer, Legend
} from 'recharts'
import { NewsImpact } from '@/components/news/NewsImpact'

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

function PortfolioNewsTab({ newsItems }: { newsItems: NewsEvent[] }) {
  const { data: positions, isLoading: posLoading } = useQuery({
    queryKey: ['trading', 'positions'],
    queryFn: () => tradingApi.positions(),
  })

  const positionAssets = useMemo(
    () => new Set(positions?.items.map(p => p.asset_id) ?? []),
    [positions],
  )

  const portfolioNews = useMemo(() => {
    if (positionAssets.size === 0) return []
    return newsItems
      .filter(item => item.asset_ids_mentioned.some(id => positionAssets.has(id)))
      .sort((a, b) => {
        const sa = a.sentiment_score ?? 0
        const sb = b.sentiment_score ?? 0
        return sa - sb // most negative first
      })
  }, [newsItems, positionAssets])

  if (posLoading) return <p className="text-gray-400">加载持仓中...</p>

  if (positionAssets.size === 0) {
    return (
      <div className="text-center text-gray-400 py-12">
        <p className="text-lg mb-1">暂无持仓</p>
        <p className="text-sm">请先在交易模块建仓后查看持仓相关新闻</p>
      </div>
    )
  }

  if (portfolioNews.length === 0) {
    return <p className="text-sm text-gray-400 py-8 text-center">暂无与持仓相关的新闻</p>
  }

  const abnormal = portfolioNews.filter(n => n.sentiment_score !== null && n.sentiment_score < -0.3)

  return (
    <div className="space-y-4">
      {abnormal.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <p className="text-sm font-medium text-red-700">
            {abnormal.length} 条持仓资产存在异常负面情绪，请关注
          </p>
        </div>
      )}

      <div className="text-xs text-gray-500">
        共 {portfolioNews.length} 条持仓相关新闻（持仓资产: {positionAssets.size} 个）
      </div>

      <div className="space-y-3">
        {portfolioNews.map(item => (
          <div key={item.event_id} className="card">
            <div className="flex items-start gap-3">
              <SentimentDot score={item.sentiment_score} />
              <div className="flex-1 min-w-0">
                <div className="font-medium text-gray-900 leading-snug">{item.headline}</div>
                <div className="flex gap-3 mt-1 text-xs text-gray-400">
                  <span>{item.source}</span>
                  <span>{item.event_type}</span>
                  <span>{item.published_at?.slice(0, 16) ?? '---'}</span>
                  {item.sentiment_score !== null && (
                    <span className={item.sentiment_score < -0.3 ? 'text-red-600 font-medium' : item.sentiment_score > 0.3 ? 'text-green-600' : ''}>
                      情绪: {item.sentiment_score.toFixed(2)}
                    </span>
                  )}
                </div>
                {item.asset_ids_mentioned.length > 0 && (
                  <div className="flex gap-1 mt-2 flex-wrap">
                    {item.asset_ids_mentioned.map(a => (
                      <span
                        key={a}
                        className={`badge text-xs ${positionAssets.has(a) ? 'bg-amber-50 text-amber-700 font-medium' : 'bg-indigo-50 text-indigo-700'}`}
                      >
                        {a}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

const tabs = [
  { id: 'timeline', label: '新闻时间线' },
  { id: 'impact', label: '影响分析' },
  { id: 'portfolio', label: '持仓新闻' },
] as const

type NewsTab = typeof tabs[number]['id']

export function NewsPage() {
  const [activeTab, setActiveTab] = useState<NewsTab>('timeline')
  const [source, setSource] = useState('')
  const [eventType, setEventType] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [assetId, setAssetId] = useState('')

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

  const { data: assetSentiment, isLoading: sentimentLoading } = useQuery({
    queryKey: ['news', 'assetSentiment', assetId],
    queryFn: () => newsApi.getAssetSentiment(assetId),
    enabled: assetId.trim().length > 0,
  })

  const sources = Object.keys(stats?.source_counts ?? {})
  const eventTypes = Object.keys(stats?.event_type_counts ?? {})

  return (
    <div>
      <h1 className="page-title">消息面</h1>
      <p className="page-subtitle">新闻事件浏览 · 情绪过滤 · 资产关联</p>

      {/* Tab Bar */}
      <div className="flex gap-1 border-b mb-6">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'timeline' && (<>
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

      {/* 情绪趋势图 */}
      {stats?.daily_sentiment && stats.daily_sentiment.length > 0 && (
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-3">情绪趋势（近30天）</h2>
          {(() => {
            const data = [...stats!.daily_sentiment].reverse()  // 时间正序
            // 计算7日/30日滚动均值
            const with7d = data.map((d, i) => {
              const win7 = data.slice(Math.max(0, i - 6), i + 1)
              const win30 = data.slice(Math.max(0, i - 29), i + 1)
              return {
                ...d,
                avg_7d: Number((win7.reduce((s, r) => s + r.avg_sentiment, 0) / win7.length).toFixed(4)),
                avg_30d: Number((win30.reduce((s, r) => s + r.avg_sentiment, 0) / win30.length).toFixed(4)),
              }
            })
            return (
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={with7d} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10 }}
                    tickFormatter={v => String(v).slice(5)}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fontSize: 10 }}
                    domain={[-1, 1]}
                    tickFormatter={v => v.toFixed(1)}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null
                      const d = payload[0].payload as { date: string; avg_sentiment: number; avg_7d: number; avg_30d: number }
                      return (
                        <div
                          className="bg-white border rounded-lg shadow-lg px-3 py-2 text-xs cursor-pointer"
                          onClick={() => setSelectedDate(selectedDate === d.date ? null : d.date)}
                        >
                          <div className="font-medium mb-1">📅 {d.date}{selectedDate === d.date ? ' ✓' : ''}</div>
                          {payload.map((p) => (
                            <div key={String(p.dataKey)} className="flex items-center gap-1.5">
                              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color ?? undefined }} />
                              <span>{p.name}: {Number(p.value).toFixed(4)}</span>
                            </div>
                          ))}
                        </div>
                      )
                    }}
                  />
                  <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="3 3" />
                  <Legend iconSize={10} wrapperStyle={{ fontSize: 11 }} />
                  <Line
                    type="monotone"
                    dataKey="avg_sentiment"
                    name="日均情绪"
                    stroke="#94a3b8"
                    dot={false}
                    strokeWidth={1}
                  />
                  <Line
                    type="monotone"
                    dataKey="avg_7d"
                    name="7日均线"
                    stroke="#3b82f6"
                    dot={false}
                    strokeWidth={2}
                  />
                  <Line
                    type="monotone"
                    dataKey="avg_30d"
                    name="30日均线"
                    stroke="#f59e0b"
                    dot={false}
                    strokeWidth={1.5}
                    strokeDasharray="4 4"
                  />
                </LineChart>
              </ResponsiveContainer>
            )
          })()}
          <p className="text-xs text-gray-400 mt-1">
            正值（蓝色区域上方）= 整体偏乐观；负值 = 偏悲观
          </p>
        </div>
      )}

      {/* 情绪热力图 */}
      {stats?.daily_sentiment && stats.daily_sentiment.length > 0 && (() => {
        const sorted = [...stats!.daily_sentiment].reverse() // 时间正序
        // 建立 date → sentiment 映射
        const sentimentMap = new Map(sorted.map(d => [d.date, d.avg_sentiment]))

        // 按周分组（周日=0 ... 周六=6）
        const weeks: { date: string; sentiment: number | null }[][] = []
        if (sorted.length > 0) {
          const firstDate = new Date(sorted[0].date + 'T00:00:00')
          // 回溯到当周周日
          const start = new Date(firstDate)
          start.setDate(start.getDate() - start.getDay())

          const lastDate = new Date(sorted[sorted.length - 1].date + 'T00:00:00')
          const end = new Date(lastDate)
          end.setDate(end.getDate() + (6 - end.getDay()))

          const cur = new Date(start)
          let week: { date: string; sentiment: number | null }[] = []
          while (cur <= end) {
            const ds = cur.toISOString().slice(0, 10)
            week.push({ date: ds, sentiment: sentimentMap.get(ds) ?? null })
            if (week.length === 7) {
              weeks.push(week)
              week = []
            }
            cur.setDate(cur.getDate() + 1)
          }
          if (week.length > 0) weeks.push(week)
        }

        const dayLabels = ['日', '一', '二', '三', '四', '五', '六']

        return (
          <div className="card mt-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-gray-800">情绪日历</h2>
              {selectedDate && (
                <button
                  className="text-xs text-blue-600 hover:underline"
                  onClick={() => setSelectedDate(null)}
                >
                  清除过滤：{selectedDate}
                </button>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="text-xs border-collapse">
                <thead>
                  <tr>
                    <th className="w-6" />
                    {weeks.map((_, wi) => (
                      <th key={wi} className="w-5 text-center text-gray-400 font-normal px-px">
                        {wi % 2 === 0 ? '' : ''}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {dayLabels.map((label, di) => (
                    <tr key={di}>
                      <td className="text-gray-400 text-right pr-1 text-[10px] leading-4">{label}</td>
                      {weeks.map((week, wi) => {
                        const cell = week[di]
                        if (!cell) return <td key={wi} className="px-px py-px"><div className="w-4 h-4" /></td>
                        const v = cell.sentiment
                        const bg = v === null
                          ? '#f3f4f6'
                          : v >= 0
                            ? `rgba(34, 197, 94, ${Math.min(v, 1) * 0.8})`
                            : `rgba(239, 68, 68, ${Math.min(-v, 1) * 0.8})`
                        const isSelected = selectedDate === cell.date
                        return (
                          <td key={wi} className="px-px py-px">
                            <div
                              className={`w-4 h-4 rounded-sm cursor-pointer border ${isSelected ? 'border-blue-600 border-2' : 'border-transparent'}`}
                              style={{ backgroundColor: bg }}
                              title={`${cell.date}: ${v !== null ? v.toFixed(3) : '无数据'}`}
                              onClick={() => setSelectedDate(selectedDate === cell.date ? null : cell.date)}
                            />
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center gap-2 mt-2 text-[10px] text-gray-400">
              <span>负面</span>
              <div className="flex gap-0.5">
                {[-0.8, -0.4, 0, 0.4, 0.8].map(v => (
                  <div
                    key={v}
                    className="w-3 h-3 rounded-sm"
                    style={{
                      backgroundColor: v === 0
                        ? '#f3f4f6'
                        : v > 0
                          ? `rgba(34, 197, 94, ${Math.min(v, 1) * 0.8})`
                          : `rgba(239, 68, 68, ${Math.min(-v, 1) * 0.8})`,
                    }}
                  />
                ))}
              </div>
              <span>正面</span>
            </div>
          </div>
        )
      })()}

      {/* Asset Sentiment */}
      <div className="card mt-4">
        <h2 className="font-semibold text-gray-800 mb-3">资产情绪分析</h2>
        <div className="flex gap-2 mb-4 items-center">
          <input
            className="input max-w-[200px]"
            placeholder="输入资产ID，如 000001.SZ"
            value={assetId}
            onChange={e => setAssetId(e.target.value)}
          />
          {assetId && sentimentLoading && <span className="text-xs text-gray-400">加载中...</span>}
        </div>
        {assetSentiment && !sentimentLoading && (assetSentiment.dates as string[]).length > 0 && (() => {
          const dates = assetSentiment.dates as string[]
          const values = assetSentiment.values as number[]
          const counts = assetSentiment.counts as number[]
          const chartData = dates.map((d, i) => ({ date: d, sentiment: values[i], count: counts[i] }))
          return (
            <div className="space-y-4">
              <div>
                <h3 className="text-sm text-gray-600 mb-2">每日情绪均值</h3>
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={chartData} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10 }}
                      tickFormatter={v => String(v).slice(5)}
                      interval="preserveStartEnd"
                    />
                    <YAxis tick={{ fontSize: 10 }} domain={[-1, 1]} tickFormatter={v => v.toFixed(1)} />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null
                        const d = payload[0].payload as { date: string; sentiment: number; count: number }
                        return (
                          <div className="bg-white border rounded-lg shadow-lg px-3 py-2 text-xs">
                            <div className="font-medium mb-1">{d.date}</div>
                            <div>情绪: {d.sentiment.toFixed(4)}</div>
                            <div>新闻数: {d.count}</div>
                          </div>
                        )
                      }}
                    />
                    <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="3 3" />
                    <Line type="monotone" dataKey="sentiment" name="情绪" stroke="#3b82f6" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div>
                <h3 className="text-sm text-gray-600 mb-2">每日新闻数量</h3>
                <ResponsiveContainer width="100%" height={120}>
                  <BarChart data={chartData} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10 }}
                      tickFormatter={v => String(v).slice(5)}
                      interval="preserveStartEnd"
                    />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null
                        const d = payload[0].payload as { date: string; count: number }
                        return (
                          <div className="bg-white border rounded-lg shadow-lg px-3 py-2 text-xs">
                            <div className="font-medium">{d.date}</div>
                            <div>新闻数: {d.count}</div>
                          </div>
                        )
                      }}
                    />
                    <Bar dataKey="count" name="新闻数" fill="#6366f1" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )
        })()}
        {assetSentiment && !sentimentLoading && (assetSentiment.dates as string[]).length === 0 && assetId.trim().length > 0 && (
          <p className="text-sm text-gray-400">该资产暂无情绪数据</p>
        )}
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-4 items-center">
        <select className="input max-w-[160px]" value={source} onChange={e => setSource(e.target.value)}>
          <option value="">全部来源</option>
          {sources.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="input max-w-[160px]" value={eventType} onChange={e => setEventType(e.target.value)}>
          <option value="">全部类型</option>
          {eventTypes.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        {selectedDate && (
          <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded flex items-center gap-1">
            日期: {selectedDate}
            <button onClick={() => setSelectedDate(null)} className="hover:text-blue-800">✕</button>
          </span>
        )}
      </div>

      {isLoading && <p className="text-gray-400">Loading…</p>}

      <div className="space-y-3">
        {!data?.items.length && !isLoading && (
          <div className="text-center text-gray-400 py-12">暂无新闻数据，请先运行 newsflow 接入</div>
        )}
        {(selectedDate ? (data?.items ?? []).filter((item: NewsEvent) => item.published_at?.startsWith(selectedDate)) : data?.items ?? []).map((item: NewsEvent) => (
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
      </>)}

      {activeTab === 'impact' && <NewsImpact />}

      {activeTab === 'portfolio' && <PortfolioNewsTab newsItems={data?.items ?? []} />}
    </div>
  )
}

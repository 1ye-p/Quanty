import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { newsApi, tradingApi, type NewsEvent } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine,
  ResponsiveContainer, Legend
} from 'recharts'
import { NewsImpact } from '@/components/news/NewsImpact'

function NewsDetail({ eventId }: { eventId: string }) {
  const { t } = useTranslation()
  const { data, isLoading } = useQuery({
    queryKey: extendedQueryKeys.news.detail(eventId),
    queryFn: () => newsApi.get(eventId),
  })

  if (isLoading) return <div className="text-gray-400 text-sm">{t('page.news.loading_detail')}</div>
  if (!data) return <div className="text-red-500 text-sm">{t('page.news.load_failed')}</div>

  return (
    <div className="space-y-2">
      {data.body && (
        <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{data.body}</div>
      )}
      {!data.body && (
        <div className="text-xs text-gray-400">{t('page.news.no_body')}</div>
      )}
    </div>
  )
}

function SentimentDot({ score }: { score: number | null }) {
  const { t } = useTranslation()
  if (score === null) return <span className="w-2 h-2 rounded-full bg-gray-300 inline-block" />
  if (score > 0.2) return <span className="w-2 h-2 rounded-full bg-green-400 inline-block" title={`${t('page.news.sentiment')}: ${score.toFixed(2)}`} />
  if (score < -0.2) return <span className="w-2 h-2 rounded-full bg-red-400 inline-block" title={`${t('page.news.sentiment')}: ${score.toFixed(2)}`} />
  return <span className="w-2 h-2 rounded-full bg-gray-400 inline-block" title={`${t('page.news.sentiment')}: ${score.toFixed(2)}`} />
}

function PortfolioNewsTab({ newsItems }: { newsItems: NewsEvent[] }) {
  const { t } = useTranslation()
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

  if (posLoading) return <p className="text-gray-400">{t('page.news.portfolio.loading')}</p>

  if (positionAssets.size === 0) {
    return (
      <div className="text-center text-gray-400 py-12">
        <p className="text-lg mb-1">{t('page.news.portfolio.no_position')}</p>
        <p className="text-sm">{t('page.news.portfolio.no_position_hint')}</p>
      </div>
    )
  }

  if (portfolioNews.length === 0) {
    return <p className="text-sm text-gray-400 py-8 text-center">{t('page.news.portfolio.no_news')}</p>
  }

  const abnormal = portfolioNews.filter(n => n.sentiment_score !== null && n.sentiment_score < -0.3)

  return (
    <div className="space-y-4">
      {abnormal.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <p className="text-sm font-medium text-red-700">
            {t('page.news.portfolio.abnormal_warning', { count: abnormal.length })}
          </p>
        </div>
      )}

      <div className="text-xs text-gray-500">
        {t('page.news.portfolio.count_summary', { count: portfolioNews.length, assets: positionAssets.size })}
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
                      {t('page.news.sentiment')}: {item.sentiment_score.toFixed(2)}
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
  { id: 'timeline', labelKey: 'page.news.tab.timeline' },
  { id: 'impact', labelKey: 'page.news.tab.impact' },
  { id: 'portfolio', labelKey: 'page.news.tab.portfolio' },
] as const

type NewsTab = typeof tabs[number]['id']

export function NewsPage() {
  const { t } = useTranslation()
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
      <h1 className="page-title">{t('page.news.title')}</h1>
      <p className="page-subtitle">{t('page.news.subtitle')}</p>

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
            {t(tab.labelKey)}
          </button>
        ))}
      </div>

      {activeTab === 'timeline' && (<>
      {/* Stats */}
      {stats && (
        <div className="flex gap-4 mb-6 flex-wrap">
          <div className="card py-3 px-5">
            <div className="text-2xl font-bold text-brand-600">{stats.total_events.toLocaleString()}</div>
            <div className="text-xs text-gray-500">{t('page.news.stat.total_events')}</div>
          </div>
          {stats.avg_sentiment !== null && (
            <div className="card py-3 px-5">
              <div className={`text-2xl font-bold ${stats.avg_sentiment > 0 ? 'text-green-600' : 'text-red-600'}`}>
                {stats.avg_sentiment.toFixed(3)}
              </div>
              <div className="text-xs text-gray-500">{t('page.news.stat.avg_sentiment')}</div>
            </div>
          )}
        </div>
      )}

      {/* 情绪趋势图 */}
      {stats?.daily_sentiment && stats.daily_sentiment.length > 0 && (
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-3">{t('page.news.trend.title')}</h2>
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
                    name={t('page.news.trend.legend.daily')}
                    stroke="#94a3b8"
                    dot={false}
                    strokeWidth={1}
                  />
                  <Line
                    type="monotone"
                    dataKey="avg_7d"
                    name={t('page.news.trend.legend.ma7')}
                    stroke="#3b82f6"
                    dot={false}
                    strokeWidth={2}
                  />
                  <Line
                    type="monotone"
                    dataKey="avg_30d"
                    name={t('page.news.trend.legend.ma30')}
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
            {t('page.news.trend.hint')}
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

        const dayLabels = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'].map(k => t(`page.news.calendar.day_labels.${k}`))

        return (
          <div className="card mt-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-gray-800">{t('page.news.calendar.title')}</h2>
              {selectedDate && (
                <button
                  className="text-xs text-blue-600 hover:underline"
                  onClick={() => setSelectedDate(null)}
                >
                  {t('page.news.calendar.clear_filter', { date: selectedDate })}
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
                              title={`${cell.date}: ${v !== null ? v.toFixed(3) : t('page.news.calendar.no_data')}`}
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
              <span>{t('page.news.calendar.legend.negative')}</span>
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
              <span>{t('page.news.calendar.legend.positive')}</span>
            </div>
          </div>
        )
      })()}

      {/* Asset Sentiment */}
      <div className="card mt-4">
        <h2 className="font-semibold text-gray-800 mb-3">{t('page.news.asset.title')}</h2>
        <div className="flex gap-2 mb-4 items-center">
          <input
            className="input max-w-[200px]"
            placeholder={t('page.news.asset.placeholder')}
            value={assetId}
            onChange={e => setAssetId(e.target.value)}
          />
          {assetId && sentimentLoading && <span className="text-xs text-gray-400">{t('common.loading')}</span>}
        </div>
        {assetSentiment && !sentimentLoading && (assetSentiment.dates as string[]).length > 0 && (() => {
          const dates = assetSentiment.dates as string[]
          const values = assetSentiment.values as number[]
          const counts = assetSentiment.counts as number[]
          const chartData = dates.map((d, i) => ({ date: d, sentiment: values[i], count: counts[i] }))
          return (
            <div className="space-y-4">
              <div>
                <h3 className="text-sm text-gray-600 mb-2">{t('page.news.asset.subtitle.daily_sentiment')}</h3>
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
                            <div>{t('page.news.asset.tooltip.sentiment')}: {d.sentiment.toFixed(4)}</div>
                            <div>{t('page.news.asset.tooltip.news_count')}: {d.count}</div>
                          </div>
                        )
                      }}
                    />
                    <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="3 3" />
                    <Line type="monotone" dataKey="sentiment" name={t('page.news.asset.tooltip.sentiment')} stroke="#3b82f6" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <div>
                <h3 className="text-sm text-gray-600 mb-2">{t('page.news.asset.subtitle.daily_count')}</h3>
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
                            <div>{t('page.news.asset.tooltip.news_count')}: {d.count}</div>
                          </div>
                        )
                      }}
                    />
                    <Bar dataKey="count" name={t('page.news.asset.tooltip.news_count')} fill="#6366f1" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )
        })()}
        {assetSentiment && !sentimentLoading && (assetSentiment.dates as string[]).length === 0 && assetId.trim().length > 0 && (
          <p className="text-sm text-gray-400">{t('page.news.asset.no_data')}</p>
        )}
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-4 items-center">
        <select className="input max-w-[160px]" value={source} onChange={e => setSource(e.target.value)}>
          <option value="">{t('page.news.filter.all_sources')}</option>
          {sources.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="input max-w-[160px]" value={eventType} onChange={e => setEventType(e.target.value)}>
          <option value="">{t('page.news.filter.all_types')}</option>
          {eventTypes.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        {selectedDate && (
          <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded flex items-center gap-1">
            {t('page.news.filter.date')}: {selectedDate}
            <button onClick={() => setSelectedDate(null)} className="hover:text-blue-800">✕</button>
          </span>
        )}
      </div>

      {isLoading && <p className="text-gray-400">{t('common.loading')}</p>}

      <div className="space-y-3">
        {!data?.items.length && !isLoading && (
          <div className="text-center text-gray-400 py-12">{t('page.news.empty')}</div>
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
                  {t('page.news.event_id')}: <code className="bg-gray-100 px-1 rounded">{item.event_id}</code>
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

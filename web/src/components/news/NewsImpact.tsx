import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { newsApi } from '@/lib/api/news'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import { cn } from '@/lib/utils'

export function NewsImpact() {
  const [selectedAsset, setSelectedAsset] = useState<string>()

  const { data: impact, isLoading, error } = useQuery({
    queryKey: extendedQueryKeys.news.impact(selectedAsset),
    queryFn: () => newsApi.getImpact({ asset: selectedAsset }),
    enabled: !!selectedAsset,
  })

  const { data: assets } = useQuery({
    queryKey: extendedQueryKeys.news.assets(),
    queryFn: () => newsApi.getAssets(),
  })

  if (isLoading) return <div className="text-center py-4 text-gray-500">加载中...</div>
  if (error) return <div className="text-center py-4 text-red-500">加载失败</div>

  return (
    <div className="space-y-6">
      {/* Asset Selector */}
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <h3 className="font-medium text-gray-800 mb-4">选择资产</h3>
        <div className="flex flex-wrap gap-2">
          {assets?.slice(0, 30).map(asset => (
            <button
              key={asset}
              onClick={() => setSelectedAsset(asset === selectedAsset ? undefined : asset)}
              className={cn(
                "px-3 py-1 rounded text-sm transition-colors",
                selectedAsset === asset
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              )}
            >
              {asset}
            </button>
          ))}
        </div>
      </div>

      {/* Impact Analysis */}
      {impact && (
        <>
          {/* Sentiment & Price Correlation */}
          <div className="bg-white rounded-xl shadow-sm border p-4">
            <h3 className="font-medium text-gray-800 mb-4">情绪与价格走势</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={impact.sentiment_price}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} tickFormatter={(v) => v.slice(5)} />
                <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
                <Tooltip />
                <Line yAxisId="left" type="monotone" dataKey="sentiment" stroke="#6366f1" name="情绪" />
                <Line yAxisId="right" type="monotone" dataKey="price" stroke="#22c55e" name="价格" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* News Event Impact */}
          <div className="bg-white rounded-xl shadow-sm border p-4">
            <h3 className="font-medium text-gray-800 mb-4">重大新闻事件影响</h3>
            <div className="space-y-3">
              {impact.events?.map((event, idx) => (
                <div key={idx} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                  <div className={cn(
                    "text-sm font-medium",
                    event.sentiment > 0 ? 'text-red-600' : event.sentiment < 0 ? 'text-green-600' : 'text-gray-500'
                  )}>
                    {event.sentiment > 0 ? '↑' : event.sentiment < 0 ? '↓' : '→'}
                  </div>
                  <div className="flex-1">
                    <div className="font-medium text-gray-800">{event.title}</div>
                    <div className="text-sm text-gray-500">{event.date}</div>
                    <div className="text-sm mt-1 text-gray-600">
                      情绪: {event.sentiment?.toFixed(2)} | 价格变化: {(event.price_change * 100)?.toFixed(2)}%
                    </div>
                  </div>
                </div>
              ))}
              {!impact.events?.length && (
                <div className="text-center text-gray-400 py-4">暂无重大新闻事件</div>
              )}
            </div>
          </div>

          {/* Sentiment Distribution */}
          <div className="bg-white rounded-xl shadow-sm border p-4">
            <h3 className="font-medium text-gray-800 mb-4">情绪分布</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={impact.sentiment_distribution}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="bucket" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#6366f1" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {/* No asset selected */}
      {!selectedAsset && (
        <div className="bg-white rounded-xl shadow-sm border p-8 text-center text-gray-400">
          选择一个资产查看新闻影响分析
        </div>
      )}
    </div>
  )
}

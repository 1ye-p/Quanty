import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { newsApi } from '@/lib/api/news'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import { cn } from '@/lib/utils'

export function NewsImpact() {
  const { t } = useTranslation()
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

  return (
    <div className="space-y-6">
      {/* Asset Selector */}
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <h3 className="font-medium text-gray-800 mb-4">{t('component.news.impact.select_asset')}</h3>
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

      {/* Loading/Error for impact */}
      {selectedAsset && isLoading && (
        <div className="text-center py-8 text-gray-500">{t('common.loading')}</div>
      )}
      {selectedAsset && error && (
        <div className="text-center py-8 text-red-500">{t('component.news.impact.load_failed_with_msg', { message: (error as Error).message })}</div>
      )}

      {/* Impact Analysis */}
      {impact && (
        <>
          {/* Sentiment & Price Correlation */}
          <div className="bg-white rounded-xl shadow-sm border p-4">
            <h3 className="font-medium text-gray-800 mb-4">{t('component.news.impact.sentiment_price_trend')}</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={impact.sentiment_price}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} tickFormatter={(v) => v.slice(5)} />
                <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
                <Tooltip />
                <Line yAxisId="left" type="monotone" dataKey="sentiment" stroke="#6366f1" name={t('component.news.impact.legend_sentiment')} />
                <Line yAxisId="right" type="monotone" dataKey="price" stroke="#22c55e" name={t('component.news.impact.legend_price')} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* News Event Impact */}
          <div className="bg-white rounded-xl shadow-sm border p-4">
            <h3 className="font-medium text-gray-800 mb-4">{t('component.news.impact.event_impact_title')}</h3>
            <div className="space-y-3">
              {impact.events?.map((event) => (
                <div key={`${event.date}-${event.title}`} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
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
                      {t('component.news.impact.event_sentiment')}: {(event.sentiment ?? 0).toFixed(2)} | {t('component.news.impact.event_price_change')}: {((event.price_change ?? 0) * 100).toFixed(2)}%
                    </div>
                  </div>
                </div>
              ))}
              {!impact.events?.length && (
                <div className="text-center text-gray-400 py-4">{t('component.news.impact.no_events')}</div>
              )}
            </div>
          </div>

          {/* Sentiment Distribution */}
          <div className="bg-white rounded-xl shadow-sm border p-4">
            <h3 className="font-medium text-gray-800 mb-4">{t('component.news.impact.sentiment_distribution')}</h3>
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
          {t('component.news.impact.select_asset_hint')}
        </div>
      )}
    </div>
  )
}

/**
 * cQuant API — News domain.
 */

import { api, type RequestConfig } from './client'

// ── Types (not yet in types/) ────────────────────────────────────────────────

export interface NewsEvent {
  event_id: string
  source: string
  headline: string
  published_at: string
  available_at: string
  asset_ids_mentioned: string[]
  sentiment_score: number | null
  event_type: string
  language: string
}

export interface NewsStats {
  total_events: number
  source_counts: Record<string, number>
  event_type_counts: Record<string, number>
  avg_sentiment: number | null
  daily_sentiment: { date: string; avg_sentiment: number; n_events: number }[]
}

// ── API ────────────────────────────────────────────────────────────────────

export const newsApi = {
  list: (params?: Record<string, string>, config?: RequestConfig) => {
    const qs = params ? '?' + new URLSearchParams(params) : ''
    return api.get<{ items: NewsEvent[]; total: number }>(`/news/events${qs}`, config)
  },

  get: (id: string, config?: RequestConfig) =>
    api.get<NewsEvent & { body?: string }>(`/news/events/${id}`, config),

  stats: (config?: RequestConfig) => api.get<NewsStats>('/news/stats', config),

  getAssetSentiment: (assetId: string, days = 90, config?: RequestConfig) =>
    api.get<Record<string, unknown>>(
      `/news/sentiment/${encodeURIComponent(assetId)}?days=${days}`,
      config,
    ),
}

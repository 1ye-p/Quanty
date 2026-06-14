/**
 * cQuant API — Knowledge base domain.
 */

import { api, type RequestConfig } from './client'

// ── Types (not yet in types/) ────────────────────────────────────────────────

export interface KnowledgeDoc {
  doc_id: string
  title: string
  source_name: string
  logical_type: string
  language: string
  ingested_at: string
}

export interface SearchHit {
  doc_id: string
  title: string
  source_name: string
  logical_type: string
  score: number
  headline: string
}

export interface SearchResponse {
  hits: SearchHit[]
  total_found: number
  latency_ms: number
}

// ── API ────────────────────────────────────────────────────────────────────

export const knowledgeApi = {
  list: (logicalType?: string, limit = 100, config?: RequestConfig) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (logicalType) params.set('logical_type', logicalType)
    return api.get<{ items: KnowledgeDoc[]; total: number }>(
      `/knowledge/docs?${params}`,
      config,
    )
  },

  get: (id: string, config?: RequestConfig) =>
    api.get<KnowledgeDoc>(`/knowledge/docs/${id}`, config),

  search: (text: string, topK = 10, config?: RequestConfig) =>
    api.post<SearchResponse>('/knowledge/search', { text, top_k: topK }, config),

  ingest: (
    body: { uri: string; logical_type?: string; source_name?: string; title?: string },
    config?: RequestConfig,
  ) => api.post('/knowledge/ingest', body, config),
}

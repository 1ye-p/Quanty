/**
 * cQuant API — Knowledge base domain.
 */

import { api, request, type RequestConfig } from './client'

// ── Types (not yet in types/) ────────────────────────────────────────────────

export interface KnowledgeDoc {
  doc_id: string
  title: string
  source_name: string
  logical_type: string
  language: string
  ingested_at: string
  tags?: string[]
  description?: string
  file_size?: number
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
  list: (params?: { tag?: string; logical_type?: string; limit?: number }, config?: RequestConfig) => {
    const sp = new URLSearchParams({ limit: String(params?.limit ?? 100) })
    if (params?.logical_type) sp.set('logical_type', params.logical_type)
    if (params?.tag) sp.set('tag', params.tag)
    return api.get<{ items: KnowledgeDoc[]; total: number }>(
      `/knowledge/docs?${sp}`,
      config,
    )
  },

  get: (id: string, config?: RequestConfig) =>
    api.get<KnowledgeDoc>(`/knowledge/docs/${id}`, config),

  upload: (file: File, metadata: { tags?: string[]; description?: string }, config?: RequestConfig) => {
    const form = new FormData()
    form.append('file', file)
    if (metadata.tags?.length) form.append('tags', JSON.stringify(metadata.tags))
    if (metadata.description) form.append('description', metadata.description)
    // Clear Content-Type so browser sets multipart/form-data with boundary
    return request<KnowledgeDoc>('/knowledge/upload', {
      method: 'POST',
      body: form as unknown as BodyInit,
      headers: {},
      ...config,
    })
  },

  update: (id: string, params: { tags?: string[]; description?: string }, config?: RequestConfig) =>
    api.patch<KnowledgeDoc>(`/knowledge/docs/${id}`, params, config),

  delete: (id: string, config?: RequestConfig) =>
    api.delete<void>(`/knowledge/docs/${id}`, config),

  getContent: (id: string, config?: RequestConfig) =>
    api.get<{ content: string; language: string }>(`/knowledge/docs/${id}/content`, config),

  getTags: (config?: RequestConfig) =>
    api.get<{ tags: string[] }>('/knowledge/tags', config),

  search: (text: string, topK = 10, config?: RequestConfig) =>
    api.post<SearchResponse>('/knowledge/search', { text, top_k: topK }, config),

  ingest: (
    body: { uri: string; logical_type?: string; source_name?: string; title?: string },
    config?: RequestConfig,
  ) => api.post('/knowledge/ingest', body, config),
}

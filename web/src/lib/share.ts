/**
 * Strategy / backtest sharing utilities.
 */

import { api } from '@/lib/api/client'

export interface SharePermissions {
  /** Allow viewers to see strategy config */
  showConfig: boolean
  /** Allow viewers to see backtest results */
  showResults: boolean
}

export interface ShareLink {
  shareId: string
  url: string
  expiresAt: string | null
}

export interface ShareContent {
  shareId: string
  type: 'backtest' | 'strategy'
  /** Backtest results or strategy config, depending on type */
  data: Record<string, unknown>
  createdAt: string
}

/**
 * Create a shareable link for a backtest run or strategy.
 */
export async function createShareLink(params: {
  type: 'backtest' | 'strategy'
  id: string
  permissions?: SharePermissions
  /** TTL in hours; null = never expires */
  expiresInHours?: number | null
}): Promise<ShareLink> {
  const res = await api.post('/share', {
    type: params.type,
    id: params.id,
    permissions: params.permissions ?? { showConfig: true, showResults: true },
    expires_in_hours: params.expiresInHours ?? null,
  })
  return res.data as ShareLink
}

/**
 * Fetch shared content by share ID (public endpoint).
 */
export async function getShareContent(shareId: string): Promise<ShareContent> {
  const res = await api.get(`/share/${shareId}`)
  return res.data as ShareContent
}

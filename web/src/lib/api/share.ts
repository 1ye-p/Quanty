/**
 * cQuant API — Share link endpoints.
 *
 * Provides create and retrieve operations for shareable content links.
 */

import { api } from './client'

// ── Types ──────────────────────────────────────────────────────────────────────

export interface ShareCreateBody {
  /** Type of content to share: 'backtest' | 'strategy' | 'factor' | 'report' */
  content_type: 'backtest' | 'strategy' | 'factor' | 'report'
  /** ID of the content to share */
  content_id: string
  /** Optional creator identifier */
  created_by?: string
}

export interface ShareCreateResponse {
  share_id: string
  url: string
}

export interface ShareContent {
  share_id: string
  content_type: string
  content_id: string
  created_by?: string
  created_at?: string
  expires_at?: string
}

// ── API ────────────────────────────────────────────────────────────────────────

export const shareApi = {
  /**
   * Create a new share link.
   *
   * @example
   * ```ts
   * const { share_id, url } = await shareApi.create({
   *   content_type: 'backtest',
   *   content_id: 'abc123',
   * })
   * ```
   */
  create: (body: ShareCreateBody) =>
    api.post<ShareCreateResponse>('/share', body),

  /**
   * Get share content by share_id.
   *
   * @example
   * ```ts
   * const share = await shareApi.get('a1b2c3d4')
   * ```
   */
  get: (shareId: string) =>
    api.get<ShareContent>(`/share/${shareId}`),
}

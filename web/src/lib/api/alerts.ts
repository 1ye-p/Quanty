/**
 * cQuant API — Alerts domain.
 */

import { api, type RequestConfig } from './client'

// ── Types (not yet in types/) ────────────────────────────────────────────────

export interface AlertRule {
  rule_id: string
  rule_type: string
  rule_type_label: string
  params: Record<string, unknown>
  enabled: boolean
  created_at: string
}

export interface AlertHistory {
  alert_id: string
  rule_id: string
  rule_type: string
  severity: string
  message: string
  triggered_at: string
  read: boolean
}

export interface NotificationChannel {
  channel_id: string
  channel_type: string
  name: string
  config: Record<string, unknown>
  enabled: boolean
  created_at: string
}

// ── API ────────────────────────────────────────────────────────────────────

export const alertsApi = {
  rules: (config?: RequestConfig) =>
    api.get<{ items: AlertRule[]; rule_types: { type: string; label: string }[] }>(
      '/alerts/rules',
      config,
    ),

  createRule: (
    body: { rule_type: string; params: Record<string, unknown>; enabled?: boolean },
    config?: RequestConfig,
  ) => api.post<{ rule_id: string; status: string }>('/alerts/rules', body, config),

  updateRule: (ruleId: string, body: Record<string, unknown>, config?: RequestConfig) =>
    api.put<{ rule_id: string; status: string }>(`/alerts/rules/${ruleId}`, body, config),

  deleteRule: (ruleId: string, config?: RequestConfig) =>
    api.delete<{ rule_id: string; status: string }>(`/alerts/rules/${ruleId}`, config),

  history: (unreadOnly = false, limit = 50, config?: RequestConfig) =>
    api.get<{ items: AlertHistory[]; unread_count: number }>(
      `/alerts/history?unread_only=${unreadOnly}&limit=${limit}`,
      config,
    ),

  markAllRead: (config?: RequestConfig) =>
    api.post<{ status: string }>('/alerts/history/read-all', undefined, config),

  check: (config?: RequestConfig) =>
    api.post<{ triggered: number }>('/alerts/check', undefined, config),

  channels: (config?: RequestConfig) =>
    api.get<{ items: NotificationChannel[] }>('/alerts/channels', config),

  createChannel: (
    body: { channel_type: string; name: string; config: Record<string, unknown>; enabled?: boolean },
    config?: RequestConfig,
  ) => api.post<{ channel_id: string; status: string }>('/alerts/channels', body, config),

  deleteChannel: (id: string, config?: RequestConfig) =>
    api.delete<{ channel_id: string; status: string }>(`/alerts/channels/${id}`, config),
}

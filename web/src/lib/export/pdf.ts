/**
 * PDF / PNG export utilities.
 *
 * Calls the backend export API and triggers a browser download.
 *
 * TODO: Backend POST /export endpoint not yet implemented.
 * Currently uses the existing GET /backtests/{run_id}/export (HTML) as fallback.
 */

import { api } from '@/lib/api/client'

export type ExportFormat = 'pdf' | 'png'
export type ExportScope = 'full' | 'tearsheet'

export interface ExportOptions {
  format: ExportFormat
  scope: ExportScope
  /** Include chart visualisations in the export */
  includeCharts?: boolean
  /** Include metrics tables */
  includeMetrics?: boolean
  /** Backtest run ID to export */
  runId?: string
}

/**
 * Request an export from the backend and trigger a file download.
 *
 * Uses `raw: true` to get the Response as a blob (the default client
 * always parses JSON, which would fail on binary data).
 */
export async function exportReport(options: ExportOptions): Promise<void> {
  const { format, scope, includeCharts = true, includeMetrics = true, runId } = options

  // TODO: Replace with POST /export when backend endpoint is implemented
  // For now, use the existing HTML export endpoint as a fallback
  const url = runId
    ? `/backtests/${runId}/export`
    : `/export`

  const res = await api.post(
    url,
    { format, scope, include_charts: includeCharts, include_metrics: includeMetrics },
    { raw: true },
  )

  const blob = await (res as Response).blob()
  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = `cquant-${scope}-${runId ?? 'report'}.${format}`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(blobUrl)
}

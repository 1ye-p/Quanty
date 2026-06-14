/**
 * PDF / PNG export utilities.
 *
 * Calls the backend export API and triggers a browser download.
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
 */
export async function exportReport(options: ExportOptions): Promise<void> {
  const { format, scope, includeCharts = true, includeMetrics = true, runId } = options

  const res = await api.post(
    '/export',
    { format, scope, include_charts: includeCharts, include_metrics: includeMetrics, run_id: runId },
    { responseType: 'blob' },
  )

  const blob = new Blob([res.data], {
    type: format === 'pdf' ? 'application/pdf' : 'image/png',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `cquant-${scope}-${runId ?? 'report'}.${format}`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

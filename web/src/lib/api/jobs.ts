/**
 * cQuant API — Jobs domain.
 */

import { api, type RequestConfig } from './client'

// ── API ────────────────────────────────────────────────────────────────────

export const jobsApi = {
  cancel: (jobId: string, config?: RequestConfig) =>
    api.post<{ job_id: string; status: string }>(
      `/jobs/${jobId}/cancel`,
      undefined,
      config,
    ),

  delete: (jobId: string, config?: RequestConfig) =>
    api.delete<{ job_id: string; status: string }>(`/jobs/${jobId}`, config),
}

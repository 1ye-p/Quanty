/**
 * cQuant API — ML domain.
 */

import { api, type RequestConfig } from './client'
import type {
  ModelInfo,
  Experiment,
  MLJob,
  TrainParams,
  DiagnosticsData,
  TrainingCurvePoint,
  PredictionBin,
} from '../types'

// Re-export types for backward compatibility
export type {
  ModelInfo as ModelCatalogInfo,
  Experiment as MLExperiment,
  MLJob,
  TrainingCurvePoint,
  PredictionBin,
  DiagnosticsData,
}

// ── API ──────────────────────────────────────────────────────────────────────

export const mlApi = {
  modelsCatalog: (config?: RequestConfig) =>
    api.get<Record<string, ModelInfo>>('/ml/models/catalog', config),

  getModelDiagnostics: (modelVersion: string, config?: RequestConfig) =>
    api.get<DiagnosticsData>(
      `/ml/models/${encodeURIComponent(modelVersion)}/diagnostics`,
      config,
    ),

  experiments: (limit = 50, config?: RequestConfig) =>
    api.get<{ items: Experiment[]; total: number; source: string }>(
      `/ml/experiments?limit=${limit}`,
      config,
    ),

  experiment: (id: string, config?: RequestConfig) =>
    api.get<Experiment>(`/ml/experiments/${id}`, config),

  featureImportance: (id: string, config?: RequestConfig) =>
    api.get<{ items: { feature: string; importance: number }[]; total: number }>(
      `/ml/experiments/${id}/feature-importance`,
      config,
    ),

  submitJob: (body: TrainParams, config?: RequestConfig) =>
    api.post<{ job_id: string; status: string }>('/ml/jobs', body, config),

  jobStatus: (id: string, config?: RequestConfig) =>
    api.get<MLJob>(`/ml/jobs/${id}`, config),

  predictions: (assetIds: string[], config?: RequestConfig) =>
    api.get<{ date: string | null; predictions: Record<string, number> }>(
      `/ml/predictions?asset_ids=${encodeURIComponent(assetIds.join(','))}`,
      config,
    ),

  predict: (
    body: { model_version: string; date?: string | null; top_n?: number },
    config?: RequestConfig,
  ) =>
    api.post<{
      date: string
      model_version: string
      trainer_name: string
      predictions: { asset_id: string; prediction: number; rank: number }[]
      total_assets: number
      top_n: number
    }>('/ml/predict', body, config),
}

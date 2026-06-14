import { z } from 'zod'

import { WalkForwardConfigSchema } from './backtest'

// ── ModelInfo (catalog entry) ──────────────────────────────────────────────

export const ModelInfoSchema = z.object({
  name: z.string(),
  display_name: z.string(),
  model_type: z.string(),
  engine: z.string(),
  description: z.string(),
  category_label: z.string(),
  default_params: z.record(z.unknown()),
  tunable_params: z.array(z.string()),
  requires_alpha360: z.boolean(),
})

export type ModelInfo = z.infer<typeof ModelInfoSchema>

// ── Experiment ─────────────────────────────────────────────────────────────

export const ExperimentSchema = z.object({
  run_id: z.string(),
  experiment_name: z.string().optional(),
  trainer_name: z.string(),
  status: z.string(),
  metrics: z.record(z.number()),
  params: z.record(z.string()),
  started_at: z.union([z.string(), z.number()]).optional(),
  completed_at: z.union([z.string(), z.number()]).optional(),
  artifact_uri: z.string().optional(),
  model_id: z.string().optional(),
  target_name: z.string().optional(),
  feature_set_version: z.string().optional(),
  error_text: z.string().optional(),
})

export type Experiment = z.infer<typeof ExperimentSchema>

// ── TrainParams ────────────────────────────────────────────────────────────

export const TrainParamsSchema = z.object({
  trainer: z.string(),
  feature_set_version: z.string(),
  target_name: z.string().optional(),
  params: z.record(z.unknown()).optional(),
  walk_forward: WalkForwardConfigSchema.optional(),
  train_ratio: z.number().optional(),
  valid_ratio: z.number().optional(),
})

export type TrainParams = z.infer<typeof TrainParamsSchema>

// ── MLJob ──────────────────────────────────────────────────────────────────

export const MLJobSchema = z.object({
  job_id: z.string(),
  trainer_name: z.string(),
  feature_set_version: z.string(),
  target_name: z.string(),
  status: z.string(),
  mlflow_run_id: z.string().optional(),
  submitted_at: z.string(),
  completed_at: z.string().optional(),
  error_text: z.string().optional(),
})

export type MLJob = z.infer<typeof MLJobSchema>

// ── ML Diagnostics ─────────────────────────────────────────────────────────

export const TrainingCurvePointSchema = z.object({
  epoch: z.number(),
  train_loss: z.number().optional(),
  valid_loss: z.number().optional(),
  valid_ic: z.number().optional(),
})

export type TrainingCurvePoint = z.infer<typeof TrainingCurvePointSchema>

export const PredictionBinSchema = z.object({
  bin_start: z.number(),
  bin_end: z.number(),
  count: z.number(),
})

export type PredictionBin = z.infer<typeof PredictionBinSchema>

export const MLDiagnosticsFoldSchema = z.object({
  fold_id: z.number(),
  run_id: z.string(),
  ic: z.number(),
  sharpe: z.number(),
  win_rate: z.number(),
})

export type MLDiagnosticsFold = z.infer<typeof MLDiagnosticsFoldSchema>

export const DiagnosticsDataSchema = z.object({
  model_version: z.string(),
  training_curve: z.array(TrainingCurvePointSchema),
  prediction_distribution: z.array(PredictionBinSchema),
  walk_forward_stability: z.array(MLDiagnosticsFoldSchema),
})

export type DiagnosticsData = z.infer<typeof DiagnosticsDataSchema>

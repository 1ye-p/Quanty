import { z } from 'zod'

// ── Strategy ───────────────────────────────────────────────────────────────

export const StrategySchema = z.object({
  strategy_id: z.string(),
  config_format: z.string(),
  config_text: z.string(),
  parsed_config: z.record(z.unknown()).optional(),
  universe_id: z.string().optional(),
  created_at: z.string(),
  updated_at: z.string(),
})

export type Strategy = z.infer<typeof StrategySchema>

// ── StrategyCreateParams ───────────────────────────────────────────────────

export const StrategyCreateParamsSchema = z.object({
  strategy_id: z.string(),
  config_text: z.string(),
  config_format: z.string().optional(),
})

// ── IndicatorSignal config shape (for reference) ─────────────────────────
// When strategy_type === 'IndicatorSignal', config_text JSON contains:
//   entry_conditions: string[]   — DSL strings for entry signals
//   exit_conditions: string[]    — DSL strings for exit signals
//   indicator_specs: { name: string; params: Record<string, number> }[]
//   max_positions: number
//   filters: { exclude_st: boolean; exclude_suspended: boolean; exclude_limit_up_down: boolean }

export type StrategyCreateParams = z.infer<typeof StrategyCreateParamsSchema>

// ── StrategyVersion ────────────────────────────────────────────────────────

export const StrategyVersionSchema = z.object({
  version_id: z.string(),
  strategy_id: z.string(),
  config_text: z.string(),
  config_format: z.string(),
  summary: z.string(),
  created_at: z.string(),
})

export type StrategyVersion = z.infer<typeof StrategyVersionSchema>

// ── OptimizationReport (from GET /strategies/{id}/optimization-report) ──────

export interface OptimizationHealth {
  status?: string
  reason?: string | null
  baseline_sharpe?: number | null
  recent_sharpe?: number | null
  baseline_ic?: number | null
  recent_ic?: number | null
}

export interface OptimizationOverfitCheck {
  baseline_psr?: number
  candidate_psr?: number
  baseline_dsr?: number
  candidate_dsr?: number
  tolerance?: number
  passed?: boolean
}

export interface OptimizationReport {
  strategy_id: string
  generated_at: string
  status: string // needs_review / skipped_healthy / skipped_no_gain / failed / applied
  reason?: string | null
  health?: OptimizationHealth | null
  best_params?: Record<string, unknown> | null
  baseline_metrics?: Record<string, number> | null
  candidate_metrics?: Record<string, number> | null
  overfit_check?: OptimizationOverfitCheck | null
}

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

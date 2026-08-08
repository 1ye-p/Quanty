import { z } from 'zod'

// ── Factor ─────────────────────────────────────────────────────────────────

export const FactorSchema = z.object({
  name: z.string(),
  description: z.string(),
  tags: z.array(z.string()),
  source: z.string().optional(),
  factor_id: z.string().optional(),
  expression: z.string().optional(),
})

export type Factor = z.infer<typeof FactorSchema>
// Alias: Factor and FactorDefinition are the same shape

// ── ICResult ───────────────────────────────────────────────────────────────

export const ICPointSchema = z.object({
  trade_date: z.string(),
  ic: z.number(),
})

export type ICPoint = z.infer<typeof ICPointSchema>

export const ICSummarySchema = z.object({
  mean_ic: z.number().optional(),
  ir: z.number().optional(),
  hit_rate: z.number().optional(),
  observations: z.number().optional(),
  rank_ic_decay: z
    .array(z.object({ lag: z.number(), ic: z.number() }))
    .optional(),
  quantile_returns: z
    .array(z.object({ quantile: z.number(), mean_return: z.number() }))
    .optional(),
  factor_turnover: z.number().optional(),
  ic_ttest: z
    .object({
      t_stat: z.number().nullable().optional(),
      p_value: z.number().nullable().optional(),
      ci_lower: z.number().nullable().optional(),
      ci_upper: z.number().nullable().optional(),
      n: z.number(),
      significant: z.boolean().optional(),
    })
    .optional(),
  ic_half_life: z.number().nullable().optional(),
})

export type ICSummary = z.infer<typeof ICSummarySchema>

export const ICResultSchema = z.object({
  job_id: z.string(),
  status: z.string(),
  series_json: z.array(ICPointSchema).optional(),
  summary_json: ICSummarySchema.optional(),
})

export type ICResult = z.infer<typeof ICResultSchema>

// ── FactorCorrelation ──────────────────────────────────────────────────────

export const FactorCorrelationSchema = z.object({
  factors: z.array(z.string()),
  matrix: z.array(
    z.object({
      factor_a: z.string(),
      factor_b: z.string(),
      correlation: z.number().nullable(),
    }),
  ),
})

export type FactorCorrelation = z.infer<typeof FactorCorrelationSchema>

// ── FactorDefinition (from API) ────────────────────────────────────────────

export const FactorDefinitionSchema = z.object({
  name: z.string(),
  description: z.string(),
  tags: z.array(z.string()),
  source: z.string().optional(),
  factor_id: z.string().optional(),
  expression: z.string().optional(),
})

export type FactorDefinition = z.infer<typeof FactorDefinitionSchema>

// ── CustomFactor ───────────────────────────────────────────────────────────

export const CustomFactorSchema = z.object({
  factor_id: z.string(),
  name: z.string(),
  expression: z.string(),
  description: z.string(),
  created_at: z.string(),
})

export type CustomFactor = z.infer<typeof CustomFactorSchema>

// ── IC Status (monitoring) ─────────────────────────────────────────────────

export const ICStatusItemSchema = z.object({
  factor_name: z.string(),
  mean_ic: z.number(),
  ir: z.number().nullable(),
  hit_rate: z.number().nullable(),
  is_alert: z.boolean(),
  alert_message: z.string().nullable(),
})

export type ICStatusItem = z.infer<typeof ICStatusItemSchema>

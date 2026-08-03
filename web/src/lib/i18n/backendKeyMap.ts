/**
 * 后端动态文本 → i18n key 映射表
 *
 * 后端 API 返回的 metric 名、风控策略名等动态文本通常是英文标识符或
 * Title Case 字符串（如 "Total Return"、"position_limit"）。本模块将其
 * 映射到结构化 i18n key，使前端在切换语言时能正确翻译这些动态字段。
 *
 * 用法：
 *   import { translateBackendKey } from '@/lib/i18n/backendKeyMap'
 *   const label = translateBackendKey(t, metricName)
 */

// ── 回测指标名 → common.metric.* ────────────────────────────────────────────
// 同时覆盖 snake_case（如 "total_return"）与 Title Case（如 "Total Return"）
const METRIC_KEYS = [
  'total_return',
  'annualized_return',
  'sharpe_ratio',
  'sortino_ratio',
  'max_drawdown',
  'win_rate',
  'information_ratio',
  'tracking_error',
  'alpha',
  'beta',
  'calmar_ratio',
  'volatility',
  'cumulative_return',
  'annual_volatility',
  'calmar',
] as const

// ── 风控策略名 → common.risk_policy.* ───────────────────────────────────────
const RISK_POLICY_KEYS = [
  'position_limit',
  'stop_loss',
  'drawdown_breaker',
  'trailing_stop',
  'atr_stop',
  'atr_stop_loss',
  'take_profit',
  'leverage_limit',
  'global_stop_loss',
  'global_take_profit',
  'global_stop',
] as const

/** 将 snake_case 转为 Title Case（"total_return" → "Total Return"） */
function toTitleCase(snake: string): string {
  return snake
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

/** 构建映射表：同时收录 snake_case 与 Title Case 两种 key 形式 */
function buildMap(): Record<string, string> {
  const map: Record<string, string> = {}

  for (const key of METRIC_KEYS) {
    const i18nKey = `common.metric.${key}`
    map[key] = i18nKey
    map[toTitleCase(key)] = i18nKey
  }

  for (const key of RISK_POLICY_KEYS) {
    // atr_stop_loss 与 atr_stop 都映射到 common.risk_policy.atr_stop（locale 中存在）
    const localeKey = key === 'atr_stop_loss' ? 'atr_stop' : key
    // global_stop 映射到 common.risk_policy.global_stop_loss
    const targetKey = key === 'global_stop' ? 'global_stop_loss' : localeKey
    const i18nKey = `common.risk_policy.${targetKey}`
    map[key] = i18nKey
    map[toTitleCase(key)] = i18nKey
  }

  return map
}

/**
 * 后端动态文本 → i18n key 映射表。
 *
 * key 形式：snake_case（"total_return"）或 Title Case（"Total Return"）。
 * value：结构化 i18n key（"common.metric.total_return"）。
 */
export const BACKEND_KEY_MAP: Record<string, string> = buildMap()

/**
 * 翻译后端动态文本。
 *
 * 若 *backendKey* 在映射表中存在，返回对应的 i18n 翻译；否则原样返回
 * *backendKey*（保证未映射的字段不会显示为空）。
 *
 * @param t i18n 翻译函数（来自 useTranslation 的 t）
 * @param backendKey 后端返回的字段名（如 "Total Return"、"position_limit"）
 * @returns 翻译后的字符串，或原样 backendKey
 *
 * @example
 *   translateBackendKey(t, 'Total Return')     // → "总收益" (zh-CN)
 *   translateBackendKey(t, 'position_limit')   // → "仓位限制" (zh-CN)
 *   translateBackendKey(t, 'unknown_field')    // → "unknown_field"
 */
export function translateBackendKey(
  t: (k: string) => string,
  backendKey: string,
): string {
  const i18nKey = BACKEND_KEY_MAP[backendKey]
  return i18nKey ? t(i18nKey) : backendKey
}

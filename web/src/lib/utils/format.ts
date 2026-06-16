/** Shared number formatting utilities for charts and metrics. */

/** Format number with locale-aware separators. */
export function formatNum(v: unknown, digits = 2): string {
  return Number(v ?? 0).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

/** Format number in short form (K/M/B). */
export function formatNumShort(v: unknown): string {
  const n = Number(v ?? 0)
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(1)}B`
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1)}K`
  return n.toFixed(0)
}

/** Format as percentage with sign. */
export function formatPct(v: unknown, digits = 2): string {
  const n = Number(v ?? 0) * 100
  return `${n >= 0 ? '+' : ''}${n.toFixed(digits)}%`
}

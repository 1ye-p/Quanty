/**
 * Shared utility functions.
 */

/** Format elapsed seconds since a timestamp as human-readable string. */
export function elapsedStr(startedAt: string | number | undefined): string {
  if (!startedAt) return '—'
  const start = typeof startedAt === 'number' ? startedAt : new Date(startedAt).getTime()
  const elapsed = Math.floor((Date.now() - start) / 1000)
  if (elapsed < 60) return `${elapsed}s`
  if (elapsed < 3600) return `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`
  return `${Math.floor(elapsed / 3600)}h ${Math.floor((elapsed % 3600) / 60)}m`
}

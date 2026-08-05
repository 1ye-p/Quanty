/**
 * Annotation grouping utilities for K-line chart markers.
 *
 * Collapses multiple trade annotations on the same date into summary markers
 * to prevent visual overlap on the chart.
 */

import type { TradeAnnotation } from './KlineChart'

/** Represents a group of annotations collapsed into a single marker. */
export interface CollapsedAnnotation {
  date: string
  count: number
  buys: number
  sells: number
  annotations: TradeAnnotation[]
  label: string
  color: string
}

/**
 * Group annotations by date.
 * Returns a Map where keys are date strings (YYYY-MM-DD) and values are arrays of annotations.
 */
export function groupAnnotationsByDate(
  annotations: TradeAnnotation[],
): Map<string, TradeAnnotation[]> {
  const grouped = new Map<string, TradeAnnotation[]>()

  for (const annotation of annotations) {
    const existing = grouped.get(annotation.time) || []
    existing.push(annotation)
    grouped.set(annotation.time, existing)
  }

  return grouped
}

/**
 * Create collapsed annotations from a list of trade annotations.
 *
 * - Single annotation per date: preserved as-is (arrowUp/arrowDown)
 * - Multiple annotations per date: collapsed into a summary marker (circle)
 *
 * @param formatLabel optional localized label builder for multi-annotation
 *   markers (buys, sells → summary text). Defaults to Chinese "N买 / M卖".
 */
export function createCollapsedAnnotations(
  annotations: TradeAnnotation[],
  formatLabel?: (buys: number, sells: number) => string,
): CollapsedAnnotation[] {
  const grouped = groupAnnotationsByDate(annotations)
  const collapsed: CollapsedAnnotation[] = []

  for (const [date, group] of grouped) {
    const buys = group.filter(a => a.shape === 'arrowUp').length
    const sells = group.filter(a => a.shape === 'arrowDown').length
    const count = group.length

    // Determine dominant color: green if more buys, red if more sells, yellow if equal
    let color: string
    if (buys > sells) {
      color = '#22c55e' // green
    } else if (sells > buys) {
      color = '#ef4444' // red
    } else {
      color = '#eab308' // yellow for balanced
    }

    // Build label
    let label: string
    if (count === 1) {
      label = group[0].text
    } else if (formatLabel) {
      label = formatLabel(buys, sells)
    } else {
      const parts: string[] = []
      if (buys > 0) parts.push(`${buys}买`)
      if (sells > 0) parts.push(`${sells}卖`)
      label = parts.join(' / ')
    }

    collapsed.push({
      date,
      count,
      buys,
      sells,
      annotations: group,
      label,
      color,
    })
  }

  // Sort by date
  return collapsed.sort((a, b) => a.date.localeCompare(b.date))
}

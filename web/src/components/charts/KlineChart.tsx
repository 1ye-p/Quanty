/**
 * KlineChart — Candlestick + Volume dual-pane chart with trade annotations.
 *
 * Uses lightweight-charts (TradingView library) to render:
 *   - CandlestickSeries for OHLC data
 *   - HistogramSeries for volume (separate pane below candlesticks)
 *   - Markers API for buy/sell trade annotations (with collapsing for same-date)
 *   - Tooltip for collapsed markers on hover
 *
 * Props:
 *   data              — OHLCV[] from market API
 *   annotations       — optional trade markers (buy/sell signals)
 *   height            — total chart height in px (default 400)
 *   defaultRangeMonths — how many months of data to show initially (default 8)
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  createChart,
  ColorType,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
  type CandlestickData,
  type HistogramData,
} from 'lightweight-charts'
import type { OHLCV } from '@/lib/api/market'
import { createCollapsedAnnotations, type CollapsedAnnotation } from './annotationUtils'
import { CollapsedMarkerTooltip } from './CollapsedMarkerTooltip'

export interface TradeAnnotation {
  time: string // YYYY-MM-DD
  position: 'aboveBar' | 'belowBar'
  color: string
  shape: 'circle' | 'square' | 'arrowUp' | 'arrowDown'
  text: string
}

interface KlineChartProps {
  data: OHLCV[]
  annotations?: TradeAnnotation[]
  height?: number
  defaultRangeMonths?: number
}

const UP_COLOR = '#22c55e'
const DOWN_COLOR = '#ef4444'
const UP_VOLUME_COLOR = 'rgba(34,197,94,0.35)'
const DOWN_VOLUME_COLOR = 'rgba(239,68,68,0.35)'

export function KlineChart({
  data,
  annotations = [],
  height = 400,
  defaultRangeMonths = 8,
}: KlineChartProps) {
  const { t } = useTranslation()
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const collapsedRef = useRef<CollapsedAnnotation[]>([])

  // Tooltip state
  const [tooltip, setTooltip] = useState<{
    annotation: CollapsedAnnotation
    x: number
    y: number
  } | null>(null)

  // Crosshair move handler for tooltip
  const handleCrosshairMove = useCallback(
    (param: {
      time?: Time
      point?: { x: number; y: number }
      seriesData: Map<ISeriesApi<any>, unknown>
    }) => {
      if (!param.time || !param.point) {
        setTooltip(null)
        return
      }

      const timeStr = param.time as string
      const collapsed = collapsedRef.current.find(c => c.date === timeStr)

      if (collapsed && collapsed.count > 1) {
        setTooltip({
          annotation: collapsed,
          x: param.point.x,
          y: param.point.y,
        })
      } else {
        setTooltip(null)
      }
    },
    [],
  )

  // Init chart
  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: '#ffffff' },
        textColor: '#6b7280',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#f3f4f6' },
        horzLines: { color: '#f3f4f6' },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: '#e5e7eb' },
      timeScale: { borderColor: '#e5e7eb', timeVisible: false },
    })
    chartRef.current = chart

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: UP_COLOR,
      downColor: DOWN_COLOR,
      borderUpColor: UP_COLOR,
      borderDownColor: DOWN_COLOR,
      wickUpColor: UP_COLOR,
      wickDownColor: DOWN_COLOR,
    })
    candleSeriesRef.current = candleSeries

    // Volume histogram series (separate price scale at the bottom)
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    })
    volumeSeriesRef.current = volumeSeries

    // Configure volume pane to occupy bottom 20% of chart
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })

    // Resize observer
    const ro = new ResizeObserver(entries => {
      const entry = entries[0]
      if (entry) chart.applyOptions({ width: entry.contentRect.width })
    })
    ro.observe(containerRef.current)

    // Subscribe to crosshair move for tooltip
    chart.subscribeCrosshairMove(handleCrosshairMove)

    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove)
      ro.disconnect()
      chart.remove()
      chartRef.current = null
      candleSeriesRef.current = null
      volumeSeriesRef.current = null
    }
  }, [height, handleCrosshairMove])

  // Update data + annotations
  useEffect(() => {
    if (!candleSeriesRef.current || !data.length) return

    // Sort by date ascending
    const sorted = [...data].sort((a, b) =>
      a.trade_date.localeCompare(b.trade_date),
    )

    // Candlestick data
    const candleData: CandlestickData[] = sorted.map(d => ({
      time: d.trade_date as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }))
    candleSeriesRef.current.setData(candleData)

    // Volume data — colored by candle direction
    const volumeData: HistogramData[] = sorted.map(d => ({
      time: d.trade_date as Time,
      value: d.volume,
      color: d.close >= d.open ? UP_VOLUME_COLOR : DOWN_VOLUME_COLOR,
    }))
    volumeSeriesRef.current?.setData(volumeData)

    // Trade annotations → collapsed markers
    if (annotations.length > 0) {
      const dateSet = new Set(sorted.map(d => d.trade_date))
      const validAnnotations = annotations.filter(a => dateSet.has(a.time))
      const collapsed = createCollapsedAnnotations(validAnnotations, (buys, sells) => {
        const parts: string[] = []
        if (buys > 0) parts.push(t('component.charts.collapsed_marker_tooltip.marker_buys', { count: buys }))
        if (sells > 0) parts.push(t('component.charts.collapsed_marker_tooltip.marker_sells', { count: sells }))
        return parts.join(t('component.charts.collapsed_marker_tooltip.marker_join'))
      })
      collapsedRef.current = collapsed

      const markers: SeriesMarker<Time>[] = collapsed.map(c => ({
        time: c.date as Time,
        position: c.count === 1 ? c.annotations[0].position : 'aboveBar',
        color: c.color,
        shape: c.count === 1 ? c.annotations[0].shape : 'circle',
        text: c.label,
      }))
      candleSeriesRef.current.setMarkers(markers)
    } else {
      collapsedRef.current = []
      candleSeriesRef.current.setMarkers([])
    }

    // Set default visible range to last N months (clamped to data range)
    if (sorted.length > 0) {
      const lastDate = sorted[sorted.length - 1].trade_date
      const firstDate = sorted[0].trade_date
      const endDate = new Date(lastDate)
      const startDate = new Date(endDate)
      startDate.setMonth(startDate.getMonth() - defaultRangeMonths)
      // Clamp to earliest available data
      const clampedStart = startDate < new Date(firstDate) ? new Date(firstDate) : startDate

      const startStr = clampedStart.toISOString().slice(0, 10)
      const endStr = endDate.toISOString().slice(0, 10)

      chartRef.current?.timeScale().setVisibleRange({
        from: startStr as Time,
        to: endStr as Time,
      })
    }
  }, [data, annotations, defaultRangeMonths, t])

  if (!data.length) {
    return (
      <div
        className="flex items-center justify-center rounded-lg bg-gray-50 text-gray-400 text-sm"
        style={{ height }}
      >
        {t('component.charts.kline.no_data')}
      </div>
    )
  }

  return (
    <div className="relative">
      <div ref={containerRef} style={{ height }} className="w-full" />
      {tooltip && (
        <CollapsedMarkerTooltip
          annotation={tooltip.annotation}
          x={tooltip.x}
          y={tooltip.y}
        />
      )}
    </div>
  )
}

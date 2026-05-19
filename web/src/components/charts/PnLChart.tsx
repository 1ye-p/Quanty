/**
 * PnLChart — NAV + Drawdown dual-pane chart using lightweight-charts (TradingView library).
 *
 * Props:
 *   data       — array of { time: string (YYYY-MM-DD), nav: number, drawdown?: number }
 *   height     — total chart height in px (default 340)
 *   navColor   — NAV line color (default #4f63d2)
 *   ddColor    — Drawdown area color (default #ef4444)
 */
import { useEffect, useRef } from 'react'
import {
  createChart,
  ColorType,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
} from 'lightweight-charts'

export interface PnLDataPoint {
  time: string    // YYYY-MM-DD
  nav: number
  drawdown?: number   // negative fraction, e.g. -0.15 = -15%
}

interface Props {
  data: PnLDataPoint[]
  height?: number
  navColor?: string
  ddColor?: string
  showDrawdown?: boolean
}

export function PnLChart({
  data,
  height = 340,
  navColor = '#4f63d2',
  ddColor = '#ef4444',
  showDrawdown = true,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const navSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ddSeriesRef = useRef<ISeriesApi<'Area'> | null>(null)

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
      timeScale: { borderColor: '#e5e7eb', timeVisible: true },
    })
    chartRef.current = chart

    // NAV line series
    const navSeries = chart.addLineSeries({
      color: navColor,
      lineWidth: 2,
      title: 'NAV',
      priceScaleId: 'right',
    })
    navSeriesRef.current = navSeries

    // Drawdown area series (optional, separate price scale)
    if (showDrawdown) {
      const ddSeries = chart.addAreaSeries({
        lineColor: ddColor,
        topColor: `${ddColor}30`,
        bottomColor: `${ddColor}00`,
        lineWidth: 1,
        title: 'Drawdown',
        priceScaleId: 'left',
        lineStyle: LineStyle.Dotted,
      })
      ddSeriesRef.current = ddSeries
    }

    // Resize observer
    const ro = new ResizeObserver(entries => {
      const entry = entries[0]
      if (entry) chart.applyOptions({ width: entry.contentRect.width })
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [height, navColor, ddColor, showDrawdown])

  // Update data
  useEffect(() => {
    if (!navSeriesRef.current || !data.length) return

    const navData = data
      .filter(d => d.nav != null && isFinite(d.nav))
      .map(d => ({ time: d.time, value: d.nav }))

    navSeriesRef.current.setData(navData)

    if (showDrawdown && ddSeriesRef.current) {
      const ddData = data
        .filter(d => d.drawdown != null && isFinite(d.drawdown!))
        .map(d => ({ time: d.time, value: (d.drawdown ?? 0) * 100 }))   // convert to %
      ddSeriesRef.current.setData(ddData)
    }

    chartRef.current?.timeScale().fitContent()
  }, [data, showDrawdown])

  if (!data.length) {
    return (
      <div
        className="flex items-center justify-center rounded-lg bg-gray-50 text-gray-400 text-sm"
        style={{ height }}
      >
        暂无时序数据
      </div>
    )
  }

  return <div ref={containerRef} style={{ height }} className="w-full" />
}

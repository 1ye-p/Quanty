/**
 * IndicatorPreview — Compute and chart selected technical indicators for an asset.
 *
 * Fetches OHLCV data for the given asset, computes selected indicators via API,
 * and renders results as a multi-line Recharts LineChart.
 */
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { indicatorsApi } from '@/lib/api'
import { DataState } from '@/components/ui/DataState'

// ── Types ────────────────────────────────────────────────────────────────────

interface SelectedIndicator {
  name: string
  params: Record<string, number>
}

export interface IndicatorPreviewProps {
  assetId: string
  indicators: SelectedIndicator[]
}

// ── Constants ────────────────────────────────────────────────────────────────

const LINE_COLORS = [
  '#6366f1', // indigo
  '#f59e0b', // amber
  '#10b981', // emerald
  '#ef4444', // red
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#84cc16', // lime
]

// ── Component ────────────────────────────────────────────────────────────────

export function IndicatorPreview({ assetId, indicators }: IndicatorPreviewProps) {
  const { t } = useTranslation()
  // Fetch OHLCV data for the asset
  const {
    data: ohlcvData,
    isLoading: ohlcvLoading,
    error: ohlcvError,
  } = useQuery({
    queryKey: ['asset-ohlcv', assetId],
    queryFn: async () => {
      // Use the realtime/asset endpoint or datasets API for OHLCV data
      const res = await fetch(`/api/v1/assets/${encodeURIComponent(assetId)}/ohlcv`)
      if (!res.ok) throw new Error(`Failed to fetch OHLCV: ${res.status}`)
      return res.json() as Promise<{ rows: Record<string, unknown>[] }>
    },
    enabled: !!assetId,
    staleTime: 120_000,
  })

  // Compute indicators when data is available
  const {
    data: computedData,
    isLoading: computeLoading,
    error: computeError,
  } = useQuery({
    queryKey: ['indicator-compute', assetId, indicators],
    queryFn: () =>
      indicatorsApi.compute({
        data: ohlcvData?.rows ?? [],
        indicators: indicators.map((ind) => ({
          name: ind.name,
          params: Object.keys(ind.params).length > 0 ? ind.params : undefined,
        })),
      }),
    enabled: !!ohlcvData?.rows?.length && indicators.length > 0,
    staleTime: 120_000,
  })

  const isLoading = ohlcvLoading || computeLoading
  const error = ohlcvError || computeError

  // Identify date column and indicator columns
  const { dateCol, indicatorCols } = useMemo(() => {
    const cols = computedData?.columns ?? []
    // Find the date-like column
    const date = cols.find((c: string) =>
      ['date', 'trade_date', 'datetime', 'time', 'timestamp'].includes(c.toLowerCase()),
    ) ?? cols[0] ?? 'date'
    // All other columns are indicator values
    const indCols = cols.filter((c: string) => c !== date)
    return { dateCol: date, indicatorCols: indCols }
  }, [computedData])

  const chartData = computedData?.rows ?? []

  if (!indicators.length) {
    return (
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <h3 className="font-semibold text-gray-900 mb-4">{t('component.indicators.preview.title')}</h3>
        <div className="flex items-center justify-center py-16 text-gray-400 text-sm">
          {t('component.indicators.preview.select_hint')}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">{t('component.indicators.preview.title')}</h3>
        <span className="text-xs text-gray-500">
          {assetId} / {indicators.length} {t('component.indicators.preview.indicator_count_suffix')}
        </span>
      </div>

      <DataState
        isLoading={isLoading}
        error={error}
        isEmpty={chartData.length === 0}
        emptyText={t('common.no_data')}
      >
        <ResponsiveContainer width="100%" height={360}>
          <LineChart data={chartData} margin={{ top: 8, right: 24, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
            <XAxis
              dataKey={dateCol}
              tick={{ fontSize: 11 }}
              tickFormatter={(v: string) => {
                // Show shorter date labels
                if (typeof v === 'string' && v.length > 7) return v.slice(5) // MM-DD
                return String(v)
              }}
              interval="preserveStartEnd"
            />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip
              labelFormatter={(label: string) => `${dateCol}: ${label}`}
              contentStyle={{ fontSize: 12 }}
            />
            <Legend
              wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
              iconType="plainline"
            />
            {indicatorCols.map((col: string, idx: number) => (
              <Line
                key={col}
                type="monotone"
                dataKey={col}
                stroke={LINE_COLORS[idx % LINE_COLORS.length]}
                strokeWidth={1.5}
                dot={false}
                name={col}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>

        {/* Summary row */}
        <div className="flex flex-wrap gap-4 text-xs text-gray-500 pt-2">
          <span>{t('component.indicators.preview.data_points')} {chartData.length}</span>
          <span>{t('component.indicators.preview.indicator_columns')} {indicatorCols.length}</span>
        </div>
      </DataState>
    </div>
  )
}

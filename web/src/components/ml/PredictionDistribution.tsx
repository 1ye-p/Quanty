/**
 * PredictionDistribution — Recharts BarChart histogram of prediction bins
 * with mean / std annotations.
 */
import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
import type { PredictionBin } from '@/lib/types/ml'

function formatNum(v: number, decimals = 4): string {
  if (!isFinite(v)) return '--'
  return v.toFixed(decimals)
}

function formatNumShort(v: number, decimals = 2): string {
  if (!isFinite(v)) return '--'
  return v.toFixed(decimals)
}

interface PredictionDistributionProps {
  bins: PredictionBin[]
}

export function PredictionDistribution({ bins }: PredictionDistributionProps) {
  const stats = useMemo(() => {
    if (!bins.length) return null

    // Estimate weighted mean and std from bin midpoints
    let totalCount = 0
    let weightedSum = 0
    for (const b of bins) {
      const mid = (b.bin_start + b.bin_end) / 2
      weightedSum += mid * b.count
      totalCount += b.count
    }
    if (totalCount === 0) return null
    const mean = weightedSum / totalCount

    let varianceSum = 0
    for (const b of bins) {
      const mid = (b.bin_start + b.bin_end) / 2
      varianceSum += b.count * (mid - mean) ** 2
    }
    const std = Math.sqrt(varianceSum / totalCount)

    return { mean, std }
  }, [bins])

  if (!bins.length) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm bg-gray-50 rounded-lg">
        No prediction distribution data
      </div>
    )
  }

  const chartData = bins.map((b, i) => ({
    bin: i,
    label: `${formatNumShort(b.bin_start)}~${formatNumShort(b.bin_end)}`,
    count: b.count,
  }))

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <h3 className="font-semibold text-gray-700 mb-2">Prediction Distribution</h3>

      {stats && (
        <div className="flex items-center gap-4 mb-3 text-xs text-gray-500">
          <span>Mean: <span className="font-mono text-gray-700">{formatNum(stats.mean)}</span></span>
          <span>Std: <span className="font-mono text-gray-700">{formatNum(stats.std)}</span></span>
          <span>Samples: <span className="font-mono text-gray-700">
            {bins.reduce((s, b) => s + b.count, 0).toLocaleString()}
          </span></span>
        </div>
      )}

      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 9 }}
            interval={Math.max(0, Math.floor(chartData.length / 8) - 1)}
            angle={-30}
            textAnchor="end"
            height={50}
          />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip
            labelFormatter={(_: string, payload: Array<{ payload?: { label?: string } }>) => {
              const label = payload?.[0]?.payload?.label
              return label ? `Range: ${label}` : ''
            }}
            formatter={(value: number) => [value.toLocaleString(), 'Count']}
          />
          {stats && (
            <ReferenceLine
              x={chartData.reduce((closest, d) => {
                const mid = (bins[d.bin].bin_start + bins[d.bin].bin_end) / 2
                const closestMid = (bins[closest].bin_start + bins[closest].bin_end) / 2
                return Math.abs(mid - stats.mean) < Math.abs(closestMid - stats.mean) ? d.bin : closest
              }, 0)}
              stroke="#ef4444"
              strokeDasharray="4 4"
              label={{
                value: 'Mean',
                position: 'top',
                fill: '#ef4444',
                fontSize: 10,
              }}
            />
          )}
          <Bar dataKey="count" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

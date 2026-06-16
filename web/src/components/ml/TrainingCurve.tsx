/**
 * TrainingCurve — Recharts LineChart showing train_loss and valid_loss
 * over epochs with overfitting detection.
 */
import { useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
import type { TrainingCurvePoint } from '@/lib/types/ml'

function formatNum(v: number, decimals = 4): string {
  if (!isFinite(v)) return '--'
  return v.toFixed(decimals)
}

interface TrainingCurveProps {
  data: TrainingCurvePoint[]
}

export function TrainingCurve({ data }: TrainingCurveProps) {
  const { bestEpoch, isOverfitting } = useMemo(() => {
    if (!data.length) return { bestEpoch: null, isOverfitting: false }

    let bestIdx = 0
    let bestLoss = Infinity
    for (let i = 0; i < data.length; i++) {
      const vl = data[i].valid_loss
      if (vl != null && vl < bestLoss) {
        bestLoss = vl
        bestIdx = i
      }
    }

    // Overfitting: valid_loss is increasing while train_loss decreases in the
    // second half of training
    const half = Math.floor(data.length / 2)
    if (data.length >= 4 && half > 0) {
      const secondHalf = data.slice(half)
      let trainDecreasing = 0
      let validIncreasing = 0
      for (let i = 1; i < secondHalf.length; i++) {
        const prevT = secondHalf[i - 1].train_loss
        const currT = secondHalf[i].train_loss
        const prevV = secondHalf[i - 1].valid_loss
        const currV = secondHalf[i].valid_loss
        if (prevT != null && currT != null && currT < prevT) trainDecreasing++
        if (prevV != null && currV != null && currV > prevV) validIncreasing++
      }
      const threshold = Math.floor(secondHalf.length * 0.5)
      return {
        bestEpoch: bestIdx < data.length ? data[bestIdx].epoch : null,
        isOverfitting: trainDecreasing > threshold && validIncreasing > threshold,
      }
    }

    return {
      bestEpoch: bestIdx < data.length ? data[bestIdx].epoch : null,
      isOverfitting: false,
    }
  }, [data])

  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm bg-gray-50 rounded-lg">
        No training curve data
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <h3 className="font-semibold text-gray-700 mb-2">Training Curve</h3>

      <div className="flex items-center gap-3 mb-3">
        <div className="flex items-center gap-1.5 text-xs">
          <span className="w-3 h-0.5 bg-blue-500 inline-block rounded" />
          <span className="text-gray-500">train_loss</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="w-3 h-0.5 bg-orange-500 inline-block rounded" />
          <span className="text-gray-500">valid_loss</span>
        </div>
      </div>

      {isOverfitting && (
        <div className="mb-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
          Potential overfitting detected: validation loss is increasing while training loss continues to decrease.
        </div>
      )}

      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="epoch" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip
            formatter={(value: number, name: string) => [
              formatNum(value),
              name === 'train_loss' ? 'Train Loss' : 'Valid Loss',
            ]}
          />
          {bestEpoch != null && (
            <ReferenceLine
              x={bestEpoch}
              stroke="#10b981"
              strokeDasharray="4 4"
              label={{
                value: `Best (ep ${bestEpoch})`,
                position: 'top',
                fill: '#10b981',
                fontSize: 10,
              }}
            />
          )}
          <Line
            type="monotone"
            dataKey="train_loss"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="valid_loss"
            stroke="#f97316"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

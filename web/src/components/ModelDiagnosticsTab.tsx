/**
 * ModelDiagnosticsTab — Model diagnostics with training curve, prediction
 * distribution histogram, and walk-forward stability chart.
 *
 * Props:
 *   modelVersion — model version string (mlflow run ID or job ID)
 */
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from 'recharts'
import { mlApi, type DiagnosticsData } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { DataState } from '@/components/ui/DataState'

interface ModelDiagnosticsTabProps {
  modelVersion: string
}

function formatNum(v: number, decimals = 4): string {
  if (!isFinite(v)) return '--'
  return v.toFixed(decimals)
}

function TrainingCurveChart({ data }: { data: DiagnosticsData['training_curve'] }) {
  const { t } = useTranslation()
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm bg-gray-50 rounded-lg">
        {t('component.model_diagnostics.no_training_curve_data')}
      </div>
    )
  }

  const hasIc = data.some(d => d.valid_ic != null)

  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <div className="flex items-center gap-1.5 text-xs">
          <span className="w-3 h-0.5 bg-blue-500 inline-block rounded" />
          <span className="text-gray-500">{t('component.model_diagnostics.legend_train_loss')}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="w-3 h-0.5 bg-red-500 inline-block rounded" />
          <span className="text-gray-500">{t('component.model_diagnostics.legend_valid_loss')}</span>
        </div>
        {hasIc && (
          <div className="flex items-center gap-1.5 text-xs">
            <span className="w-3 h-0.5 bg-green-500 inline-block rounded" />
            <span className="text-gray-500">{t('component.model_diagnostics.legend_valid_ic')}</span>
          </div>
        )}
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="epoch" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip
            formatter={(value: number, name: string) => [
              formatNum(value),
              name === 'train_loss' ? t('component.model_diagnostics.tooltip_train_loss')
                : name === 'valid_loss' ? t('component.model_diagnostics.tooltip_valid_loss')
                : t('component.model_diagnostics.tooltip_valid_ic'),
            ]}
          />
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
            stroke="#ef4444"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
          {hasIc && (
            <Line
              type="monotone"
              dataKey="valid_ic"
              stroke="#10b981"
              strokeWidth={2}
              dot={false}
              connectNulls
              yAxisId={0}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function PredictionDistributionChart({ data }: { data: DiagnosticsData['prediction_distribution'] }) {
  const { t } = useTranslation()
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm bg-gray-50 rounded-lg">
        {t('component.model_diagnostics.no_prediction_dist_data')}
      </div>
    )
  }

  // Format bin labels for display
  const chartData = data.map((b, i) => ({
    bin: i,
    label: `${formatNum(b.bin_start, 2)}~${formatNum(b.bin_end, 2)}`,
    count: b.count,
  }))

  return (
    <ResponsiveContainer width="100%" height={260}>
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
            return label ? t('component.model_diagnostics.tooltip_range', { label }) : ''
          }}
          formatter={(value: number) => [value.toLocaleString(), t('component.model_diagnostics.tooltip_count')]}
        />
        <Bar dataKey="count" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function WalkForwardStabilityChart({ data }: { data: DiagnosticsData['walk_forward_stability'] }) {
  const { t } = useTranslation()
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm bg-gray-50 rounded-lg">
        {t('component.model_diagnostics.no_walk_forward_data')}
      </div>
    )
  }

  const chartData = data.map(f => ({
    fold: `Fold ${f.fold_id}`,
    IC: f.ic,
    Sharpe: f.sharpe,
    'Win Rate': f.win_rate,
  }))

  return (
    <div>
      <div className="flex items-center gap-4 mb-2">
        <div className="flex items-center gap-1.5 text-xs">
          <span className="w-3 h-0.5 bg-blue-500 inline-block rounded" />
          <span className="text-gray-500">{t('component.model_diagnostics.legend_ic')}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="w-3 h-0.5 bg-orange-500 inline-block rounded" />
          <span className="text-gray-500">{t('component.model_diagnostics.legend_sharpe')}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="w-3 h-0.5 bg-green-500 inline-block rounded" />
          <span className="text-gray-500">{t('component.model_diagnostics.legend_win_rate')}</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={chartData} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="fold" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip formatter={(value: number, name: string) => [formatNum(value, 4), name]} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey="IC" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
          <Line type="monotone" dataKey="Sharpe" stroke="#f97316" strokeWidth={2} dot={{ r: 3 }} />
          <Line type="monotone" dataKey="Win Rate" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export function ModelDiagnosticsTab({ modelVersion }: ModelDiagnosticsTabProps) {
  const { t } = useTranslation()
  const { data, isLoading, error } = useQuery({
    queryKey: extendedQueryKeys.ml.diagnostics(modelVersion),
    queryFn: () => mlApi.getModelDiagnostics(modelVersion),
    enabled: !!modelVersion,
    staleTime: 120_000,
  })

  const hasAnyData = data && (
    data.training_curve.length > 0 ||
    data.prediction_distribution.length > 0 ||
    data.walk_forward_stability.length > 0
  )

  return (
    <DataState
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && !hasAnyData}
      emptyText={t('component.model_diagnostics.no_data')}
    >
      {data && (
        <div className="space-y-6">
          {/* Training Curve */}
          <div className="card">
            <h3 className="font-semibold text-gray-700 mb-3">{t('component.model_diagnostics.training_curve_title')}</h3>
            <TrainingCurveChart data={data.training_curve} />
          </div>

          {/* Prediction Distribution */}
          <div className="card">
            <h3 className="font-semibold text-gray-700 mb-3">{t('component.model_diagnostics.prediction_dist_title')}</h3>
            <PredictionDistributionChart data={data.prediction_distribution} />
          </div>

          {/* Walk-Forward Stability */}
          <div className="card">
            <h3 className="font-semibold text-gray-700 mb-3">{t('component.model_diagnostics.walk_forward_title')}</h3>
            <WalkForwardStabilityChart data={data.walk_forward_stability} />
          </div>
        </div>
      )}
    </DataState>
  )
}

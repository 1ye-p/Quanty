/**
 * EfficientFrontierChart — Scatter chart showing the efficient frontier.
 *
 * Displays:
 * - Frontier curve (blue connected dots)
 * - Max Sharpe portfolio (red large dot with label)
 * - Min Variance portfolio (green dot)
 * - Individual assets (gray small dots with labels)
 */
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
  Label,
  type TooltipProps,
} from 'recharts'

interface FrontierPoint {
  expected_return: number
  volatility: number
  sharpe: number
}

interface IndividualAsset {
  asset: string
  expected_return: number
  volatility: number
}

interface EfficientFrontierChartProps {
  frontierPoints: FrontierPoint[]
  optimalPoint: FrontierPoint
  minVariancePoint: FrontierPoint
  individualAssets: IndividualAsset[]
  onPointClick?: (point: FrontierPoint) => void
}

interface ChartDataPoint extends FrontierPoint {
  name: string
  size: number
  fill: string
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

interface ScatterTooltipPayload {
  payload?: ChartDataPoint & { asset?: string }
}

function FrontierTooltip({ active, payload }: TooltipProps<number, string>) {
  const { t } = useTranslation()
  if (!active || !payload?.length) return null
  const point = (payload[0] as unknown as ScatterTooltipPayload)?.payload
  if (!point) return null

  return (
    <div className="bg-white rounded-lg shadow-lg border border-gray-200 p-3 text-xs min-w-[160px]">
      {point.asset && (
        <p className="font-semibold text-gray-800 mb-1">{point.asset}</p>
      )}
      <div className="space-y-1">
        <div className="flex justify-between">
          <span className="text-gray-500">{t('component.optimize.efficient_frontier.tooltip_expected_return')}</span>
          <span className="text-gray-800 font-medium">{formatPct(point.expected_return)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">{t('component.optimize.efficient_frontier.tooltip_volatility')}</span>
          <span className="text-gray-800 font-medium">{formatPct(point.volatility)}</span>
        </div>
        <div className="flex justify-between border-t border-gray-100 pt-1 mt-1">
          <span className="text-gray-500">{t('component.optimize.efficient_frontier.tooltip_sharpe')}</span>
          <span className="text-blue-700 font-semibold">{point.sharpe.toFixed(3)}</span>
        </div>
      </div>
    </div>
  )
}

function AssetTooltip({ active, payload }: TooltipProps<number, string>) {
  const { t } = useTranslation()
  if (!active || !payload?.length) return null
  const asset = (payload[0] as unknown as ScatterTooltipPayload)?.payload
  if (!asset) return null

  return (
    <div className="bg-white rounded-lg shadow-lg border border-gray-200 p-3 text-xs min-w-[140px]">
      <p className="font-semibold text-gray-800 mb-1">{asset.asset}</p>
      <div className="space-y-1">
        <div className="flex justify-between">
          <span className="text-gray-500">{t('component.optimize.efficient_frontier.tooltip_expected_return')}</span>
          <span className="text-gray-800 font-medium">{formatPct(asset.expected_return)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">{t('component.optimize.efficient_frontier.tooltip_volatility')}</span>
          <span className="text-gray-800 font-medium">{formatPct(asset.volatility)}</span>
        </div>
      </div>
    </div>
  )
}

function OptimalDot(props: { cx?: number; cy?: number }) {
  const { cx = 0, cy = 0 } = props
  return (
    <g>
      <circle cx={cx} cy={cy} r={8} fill="#ef4444" stroke="#dc2626" strokeWidth={2} />
      <circle cx={cx} cy={cy} r={12} fill="none" stroke="#ef4444" strokeWidth={1} opacity={0.3} />
    </g>
  )
}

function MinVarianceDot(props: { cx?: number; cy?: number }) {
  const { cx = 0, cy = 0 } = props
  return (
    <circle cx={cx} cy={cy} r={6} fill="#10b981" stroke="#059669" strokeWidth={2} />
  )
}

function FrontierDot(props: { cx?: number; cy?: number }) {
  const { cx = 0, cy = 0 } = props
  return (
    <circle cx={cx} cy={cy} r={4} fill="#3b82f6" stroke="#2563eb" strokeWidth={1} opacity={0.8} />
  )
}

function AssetDot(props: { cx?: number; cy?: number; payload?: IndividualAsset }) {
  const { cx = 0, cy = 0, payload } = props
  return (
    <g>
      <circle cx={cx} cy={cy} r={3} fill="#9ca3af" stroke="#6b7280" strokeWidth={1} opacity={0.7} />
      {payload?.asset && (
        <text x={cx} y={cy - 8} textAnchor="middle" fontSize={10} fill="#6b7280">
          {payload.asset}
        </text>
      )}
    </g>
  )
}

export function EfficientFrontierChart({
  frontierPoints,
  optimalPoint,
  minVariancePoint,
  individualAssets,
  onPointClick,
}: EfficientFrontierChartProps) {
  const { t } = useTranslation()
  const chartData = useMemo(() => {
    const frontier: ChartDataPoint[] = frontierPoints.map((p, i) => ({
      ...p,
      name: `point-${i}`,
      size: 40,
      fill: '#3b82f6',
    }))

    const optimal: ChartDataPoint[] = [{
      ...optimalPoint,
      name: 'optimal',
      size: 120,
      fill: '#ef4444',
    }]

    const minVar: ChartDataPoint[] = [{
      ...minVariancePoint,
      name: 'min-variance',
      size: 80,
      fill: '#10b981',
    }]

    return { frontier, optimal, minVar }
  }, [frontierPoints, optimalPoint, minVariancePoint])

  const handleClick = (data: unknown) => {
    if (!onPointClick || !data) return
    const point = data as ChartDataPoint
    onPointClick({
      expected_return: point.expected_return,
      volatility: point.volatility,
      sharpe: point.sharpe,
    })
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-800">{t('component.optimize.efficient_frontier.title')}</h3>
        <div className="flex items-center gap-4 text-xs text-gray-600">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-blue-500" />
            <span>{t('component.optimize.efficient_frontier.legend_frontier')}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <span>{t('component.optimize.efficient_frontier.legend_max_sharpe')}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-emerald-500" />
            <span>{t('component.optimize.efficient_frontier.legend_min_variance')}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-gray-400" />
            <span>{t('component.optimize.efficient_frontier.legend_assets')}</span>
          </div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={400}>
        <ScatterChart margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis
            dataKey="volatility"
            type="number"
            name="Volatility"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`}
          >
            <Label value={t('component.optimize.efficient_frontier.axis_volatility')} position="bottom" offset={5} style={{ fill: '#6b7280', fontSize: 12 }} />
          </XAxis>
          <YAxis
            dataKey="expected_return"
            type="number"
            name="Expected Return"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`}
          >
            <Label value={t('component.optimize.efficient_frontier.axis_expected_return')} angle={-90} position="left" offset={5} style={{ fill: '#6b7280', fontSize: 12 }} />
          </YAxis>
          <ZAxis dataKey="size" range={[40, 120]} />
          <Tooltip content={<FrontierTooltip />} cursor={false} />

          {/* Frontier curve */}
          <Scatter
            name="Frontier"
            data={chartData.frontier}
            shape={<FrontierDot />}
            onClick={handleClick}
            cursor="pointer"
          />

          {/* Min Variance portfolio */}
          <Scatter
            name="Min Variance"
            data={chartData.minVar}
            shape={<MinVarianceDot />}
          />

          {/* Max Sharpe portfolio */}
          <Scatter
            name="Max Sharpe"
            data={chartData.optimal}
            shape={<OptimalDot />}
          />
        </ScatterChart>
      </ResponsiveContainer>

      {/* Max Sharpe label */}
      <div className="flex justify-center mt-2">
        <div className="text-xs text-gray-600 bg-red-50 px-3 py-1 rounded-full">
          <span className="font-semibold text-red-700">
            {t('component.optimize.efficient_frontier.max_sharpe_summary', {
              ret: formatPct(optimalPoint.expected_return),
              vol: formatPct(optimalPoint.volatility),
              sharpe: optimalPoint.sharpe.toFixed(3),
            })}
          </span>
        </div>
      </div>

      {/* Individual assets chart */}
      {individualAssets.length > 0 && (
        <div className="mt-6 pt-4 border-t border-gray-100">
          <h4 className="text-sm font-medium text-gray-700 mb-3">{t('component.optimize.efficient_frontier.assets_vs_frontier')}</h4>
          <ResponsiveContainer width="100%" height={200}>
            <ScatterChart margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis
                dataKey="volatility"
                type="number"
                name="Volatility"
                tick={{ fontSize: 10, fill: '#6b7280' }}
                axisLine={{ stroke: '#e5e7eb' }}
                tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`}
              />
              <YAxis
                dataKey="expected_return"
                type="number"
                name="Expected Return"
                tick={{ fontSize: 10, fill: '#6b7280' }}
                axisLine={{ stroke: '#e5e7eb' }}
                tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`}
              />
              <ZAxis dataKey="size" range={[30, 30]} />
              <Tooltip content={<AssetTooltip />} cursor={false} />
              <Scatter
                name="Assets"
                data={individualAssets.map(a => ({ ...a, size: 30 }))}
                shape={<AssetDot />}
              />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

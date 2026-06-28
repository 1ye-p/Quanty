import { MetricCard } from '../../components/ui/MetricCard'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { backtestsApi, backtestExtApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { toast } from 'sonner'
import { useState } from 'react'
import {
  BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
  Cell, ReferenceLine,
} from 'recharts'


function FoldMetricsCard({ folds }: { folds: Record<string, unknown>[] }) {
  if (!folds || folds.length === 0) return null
  return (
    <div className="card">
      <h3 className="font-semibold text-gray-800 mb-3">Walk-Forward Fold Metrics</h3>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {folds.map((fold, i) => {
          const metrics = fold.metrics_json as Record<string, number> | null
          const sharpe = metrics?.sharpe ?? 0
          const ret = metrics?.total_return ?? 0
          return (
            <div key={i} className={`text-center p-3 rounded-lg ${sharpe > 0 ? 'bg-green-50' : 'bg-red-50'}`}>
              <div className="text-xs text-gray-500 mb-1">Fold {i + 1}</div>
              <div className={`text-lg font-bold ${sharpe > 0 ? 'text-green-700' : 'text-red-700'}`}>
                {sharpe.toFixed(2)}
              </div>
              <div className="text-xs text-gray-400">Sharpe</div>
              <div className={`text-sm mt-1 ${ret > 0 ? 'text-green-600' : 'text-red-600'}`}>
                {(ret * 100).toFixed(1)}%
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function OverfitScore({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = score > 0.7 ? 'bg-red-500' : score > 0.4 ? 'bg-yellow-500' : 'bg-green-500'
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">Overfit Score</span>
        <span className={`badge ${score > 0.7 ? 'bg-red-100 text-red-800' : score > 0.4 ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'}`}>
          {pct}%
        </span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <div className="text-xs text-gray-400 mt-1">
        {score > 0.7 ? 'Significant overfitting detected' : score > 0.4 ? 'Mild overfitting' : 'Low overfit risk'}
      </div>
    </div>
  )
}

export function BacktestOverfittingTab() {
  const { id: selectedId } = useParams<{ id: string }>()
  const [cpcvEmbargoDays, setCpcvEmbargoDays] = useState(0)

  const { data: analysisData } = useQuery({
    queryKey: queryKeys.backtests.analysis(selectedId!),
    queryFn: () => backtestsApi.getAnalysis(selectedId!),
    enabled: !!selectedId,
    staleTime: 60_000,
    retry: false,
  })

  const { data: validationData } = useQuery({
    queryKey: queryKeys.backtests.validationWindows(selectedId!),
    queryFn: () => backtestExtApi.validationWindows(selectedId!),
    enabled: !!selectedId,
  })

  const { data: multipleTestData } = useQuery({
    queryKey: queryKeys.backtests.multipleTesting(selectedId!),
    queryFn: () => backtestExtApi.multipleTesting(selectedId!),
    enabled: !!selectedId,
  })

  const analysis = analysisData as Record<string, unknown> | null | undefined
  const overfitScore = Number(analysis?.overall_overfit_score ?? 0)
  const psr = Number(analysis?.psr ?? 0)
  const dsr = Number(analysis?.dsr ?? 0)

  const wfWindows = validationData?.walk_forward ?? []
  const cpvcWindows = validationData?.cpcv ?? []

  const wfChartData = wfWindows.map((w: Record<string, unknown>, i: number) => ({
    window: `W${i + 1}`,
    sharpe: Number((w.metrics_json as Record<string, number> | null)?.sharpe ?? 0),
  }))

  if (!selectedId) return null

  return (
    <div className="space-y-4">
      {analysis && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <OverfitScore score={overfitScore} />
          <MetricCard label="PSR (Prob. Sharpe)" value={psr.toFixed(3)} sub="Closer to 1 is better" warn={psr < 0.5} />
          <MetricCard label="DSR (Deflated Sharpe)" value={dsr.toFixed(3)} sub="Multi-test corrected" warn={dsr < 0.5} />
        </div>
      )}

      {wfWindows.length > 0 && (
        <FoldMetricsCard folds={wfWindows as Record<string, unknown>[]} />
      )}

      {wfChartData.length > 0 && (
        <div className="card">
          <h3 className="font-semibold text-gray-800 mb-3">Walk-Forward OOS Sharpe ({wfChartData.length} windows)</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={wfChartData}>
              <XAxis dataKey="window" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => v.toFixed(3)} />
              <ReferenceLine y={0} stroke="#e5e7eb" />
              <Bar dataKey="sharpe" name="Sharpe">
                {wfChartData.map((_: unknown, i: number) => (
                  <Cell key={i} fill={wfChartData[i].sharpe > 0 ? '#4f63d2' : '#ef4444'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {cpvcWindows.length > 0 && (
        <div className="card">
          <h3 className="font-semibold text-gray-800 mb-3">CPCV Validation Windows ({cpvcWindows.length} combos)</h3>
          <div className="grid grid-cols-4 gap-2">
            {(cpvcWindows as Record<string, unknown>[]).slice(0, 8).map((w, i) => {
              const metrics = w.metrics_json as Record<string, number> | null
              const sr = metrics?.sharpe ?? 0
              return (
                <div key={i} className={`text-center p-2 rounded-lg text-xs ${sr > 0 ? 'bg-green-50' : 'bg-red-50'}`}>
                  <div className={`font-bold ${sr > 0 ? 'text-green-700' : 'text-red-700'}`}>{sr.toFixed(2)}</div>
                  <div className="text-gray-400">C{i + 1}</div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {multipleTestData && Object.keys(multipleTestData).length > 0 && (
        <div className="card">
          <h3 className="font-semibold text-gray-800 mb-3">Multiple Testing Correction</h3>
          <div className="space-y-2">
            {Object.entries(multipleTestData).map(([method, result]) => {
              const r = result as Record<string, unknown>
              return (
                <div key={method} className="flex items-center justify-between text-sm">
                  <span className="text-gray-600 capitalize">{method.replace('_', '-')}</span>
                  <span className={`badge ${r.any_significant ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                    {r.any_significant ? 'Significant' : 'Not significant'}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {!analysis && !validationData && !multipleTestData && (
        <div className="card text-center py-12">
          <div className="text-4xl mb-3">Lab</div>
          <div className="text-gray-500 mb-2">No overfitting analysis data available</div>
          <p className="text-xs text-gray-400 mb-4">
            Analysis runs automatically after backtest completion. Trigger manually if not yet generated.
          </p>
          <div className="flex flex-col items-center gap-3">
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-600">CPCV Embargo Days:</label>
              <input
                type="number"
                className="input w-20 text-sm"
                value={cpcvEmbargoDays}
                onChange={e => setCpcvEmbargoDays(Math.max(0, Number(e.target.value)))}
                min={0}
                max={30}
              />
              <span className="text-xs text-gray-400">Exclude N days after each test fold from training set</span>
            </div>
            <button
              className="btn-primary"
              onClick={async () => {
                try {
                  await backtestsApi.triggerAnalysis(selectedId!, { embargo_days: cpcvEmbargoDays })
                  toast.info('Analysis task submitted, check results in ~30 seconds')
                } catch (e) {
                  toast.error(`Failed to trigger analysis: ${(e as Error).message}`)
                }
              }}
            >
              Re-run Analysis
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-2">Analysis includes PSR/DSR/CPCV overfitting detection</p>
        </div>
      )}
    </div>
  )
}

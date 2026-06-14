/**
 * Deploy wizard modal for deploying a backtested strategy as a paper-trading strategy.
 * Three-step wizard: confirm backtest -> configure risk -> confirm deploy.
 */
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { liveApi } from '@/lib/api'
import { toast } from 'sonner'

interface DeployWizardProps {
  selectedId: string
  detail: Record<string, unknown>
  onClose: () => void
}

export function DeployWizard({ selectedId, detail, onClose }: DeployWizardProps) {
  const qc = useQueryClient()
  const [step, setStep] = useState(1)
  const [cash, setCash] = useState('1000000')
  const [riskMode, setRiskMode] = useState<'conservative' | 'moderate' | 'aggressive'>('conservative')
  const [checklist, setChecklist] = useState({
    confirmBacktest: false,
    understandPaper: false,
    reviewRisk: false,
  })

  const deployMutation = useMutation({
    mutationFn: (body: { backtest_run_id: string; initial_cash: number; risk_mode: string }) => liveApi.deploy(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['live', 'deployed'] })
      toast.success('Strategy deployed to paper trading. Check "Live Monitor" for status.')
      onClose()
    },
    onError: (e: Error) => toast.error(`Deploy failed: ${e.message}`),
  })

  const riskDetails: Record<string, string[]> = {
    conservative: ['Stop loss: 5%', 'Max drawdown: 10%', 'Single position cap: 10% NAV', 'Low-frequency rebalance'],
    moderate: ['Stop loss: 8%', 'Max drawdown: 15%', 'Single position cap: 15% NAV', 'Medium-frequency rebalance'],
    aggressive: ['Stop loss: 15%', 'Max drawdown: 25%', 'Single position cap: 20% NAV', 'No turnover limit'],
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="font-semibold text-gray-900">Deploy as Paper Strategy</h2>
          <div className="flex gap-1">
            {[1, 2, 3].map(s => (
              <span key={s} className={`w-6 h-6 rounded-full text-xs flex items-center justify-center ${
                s === step ? 'bg-brand-600 text-white' :
                s < step ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-500'
              }`}>{s < step ? '✓' : s}</span>
            ))}
          </div>
        </div>

        <div className="p-4">
          {step === 1 && (
            <div className="space-y-3">
              <h3 className="font-medium text-gray-800">Step 1: Confirm Backtest</h3>
              <div className="p-3 bg-gray-50 rounded-lg text-sm space-y-1">
                <div><span className="text-gray-500">Strategy: </span><strong>{String(detail.strategy_id)}</strong></div>
                <div><span className="text-gray-500">Run ID: </span><span className="font-mono text-xs">{selectedId.slice(0, 16)}...</span></div>
                <div><span className="text-gray-500">Dataset: </span>{String(detail.dataset_version)}</div>
                {(detail.metrics as Record<string, number>)?.sharpe_ratio != null && (
                  <div>
                    <span className="text-gray-500">Sharpe: </span>
                    <strong className="text-brand-600">{Number((detail.metrics as Record<string, number>).sharpe_ratio).toFixed(3)}</strong>
                  </div>
                )}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-3">
              <h3 className="font-medium text-gray-800">Step 2: Configure Capital & Risk</h3>
              <div>
                <label className="block text-xs text-gray-600 mb-1">Initial Capital</label>
                <input type="number" value={cash} onChange={e => setCash(e.target.value)}
                  className="input w-full" min={10000} step={10000} />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">Risk Mode</label>
                <select value={riskMode} onChange={e => setRiskMode(e.target.value as typeof riskMode)}
                  className="input w-full">
                  <option value="conservative">Conservative</option>
                  <option value="moderate">Moderate</option>
                  <option value="aggressive">Aggressive</option>
                </select>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg text-xs space-y-1 text-gray-600">
                <div className="font-medium text-gray-700 mb-1">Risk Parameters</div>
                {riskDetails[riskMode].map((d, i) => <div key={i}>- {d}</div>)}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-3">
              <h3 className="font-medium text-gray-800">Step 3: Confirm Deploy</h3>
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm space-y-1">
                <div>Strategy: <strong>{String(detail.strategy_id)}</strong></div>
                <div>Capital: <strong>{Number(cash).toLocaleString()}</strong></div>
                <div>Risk Mode: <strong>{riskMode}</strong></div>
              </div>
              <div className="space-y-2">
                {[
                  { key: 'confirmBacktest', label: `I confirm backtest results are satisfactory (Sharpe: ${Number((detail.metrics as Record<string, number>)?.sharpe_ratio ?? 0).toFixed(3)})` },
                  { key: 'understandPaper', label: 'I understand this is paper trading (no real trades)' },
                  { key: 'reviewRisk', label: 'I have reviewed the risk parameters' },
                ].map(({ key, label }) => (
                  <label key={key} className="flex items-start gap-2 text-xs text-gray-600 cursor-pointer">
                    <input type="checkbox"
                      checked={checklist[key as keyof typeof checklist]}
                      onChange={e => setChecklist(c => ({ ...c, [key]: e.target.checked }))}
                      className="mt-0.5 w-4 h-4 rounded border-gray-300 accent-brand-600" />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-between p-4 border-t">
          <button
            onClick={() => step > 1 ? setStep(s => s - 1) : onClose()}
            className="btn-secondary text-sm"
          >
            {step === 1 ? 'Cancel' : '< Back'}
          </button>
          {step < 3 ? (
            <button onClick={() => setStep(s => s + 1)} className="btn-primary text-sm">
              {'Next >'}
            </button>
          ) : (
            <button
              onClick={() => deployMutation.mutate({
                backtest_run_id: selectedId,
                initial_cash: Number(cash),
                risk_mode: riskMode,
              })}
              disabled={deployMutation.isPending || !checklist.confirmBacktest || !checklist.understandPaper || !checklist.reviewRisk}
              className="btn-primary text-sm disabled:opacity-40"
            >
              {deployMutation.isPending ? 'Deploying...' : 'Confirm Deploy'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

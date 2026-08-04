/**
 * Deploy wizard modal for deploying a backtested strategy as a paper-trading strategy.
 * Three-step wizard: confirm backtest -> configure risk -> confirm deploy.
 */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { liveApi } from '@/lib/api'
import { toast } from 'sonner'

interface DeployWizardProps {
  selectedId: string
  detail: Record<string, unknown>
  onClose: () => void
}

export function DeployWizard({ selectedId, detail, onClose }: DeployWizardProps) {
  const { t } = useTranslation()
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
      toast.success(t('component.backtest_overview.deploy.success_toast'))
      onClose()
    },
    onError: (e: Error) => toast.error(t('component.backtest_overview.deploy.failed_toast', { message: e.message })),
  })

  const riskDetailConfig: Record<string, { stopLoss: string; maxDD: string; cap: string; rebalanceKey: string }> = {
    conservative: { stopLoss: '5%', maxDD: '10%', cap: '10%', rebalanceKey: 'component.backtests.deploy_wizard.detail_rebalance_low' },
    moderate: { stopLoss: '8%', maxDD: '15%', cap: '15%', rebalanceKey: 'component.backtests.deploy_wizard.detail_rebalance_medium' },
    aggressive: { stopLoss: '15%', maxDD: '25%', cap: '20%', rebalanceKey: 'component.backtests.deploy_wizard.detail_no_turnover_limit' },
  }
  const riskDetails = riskDetailConfig[riskMode]
  const riskDetailItems = [
    t('component.backtests.deploy_wizard.detail_stop_loss', { value: riskDetails.stopLoss }),
    t('component.backtests.deploy_wizard.detail_max_drawdown', { value: riskDetails.maxDD }),
    t('component.backtests.deploy_wizard.detail_position_cap', { value: riskDetails.cap }),
    t(riskDetails.rebalanceKey),
  ]

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="font-semibold text-gray-900">{t('component.backtest_overview.deploy.modal_title')}</h2>
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
              <h3 className="font-medium text-gray-800">{t('component.backtest_overview.deploy.step1_title')}</h3>
              <div className="p-3 bg-gray-50 rounded-lg text-sm space-y-1">
                <div><span className="text-gray-500">{t('component.backtest_overview.deploy.strategy')} </span><strong>{String(detail.strategy_id)}</strong></div>
                <div><span className="text-gray-500">{t('component.backtest_overview.deploy.run_id')} </span><span className="font-mono text-xs">{selectedId.slice(0, 16)}...</span></div>
                <div><span className="text-gray-500">{t('component.backtest_overview.deploy.dataset')} </span>{String(detail.dataset_version)}</div>
                {(detail.metrics as Record<string, number>)?.sharpe_ratio != null && (
                  <div>
                    <span className="text-gray-500">{t('component.backtest_overview.deploy.sharpe')} </span>
                    <strong className="text-brand-600">{Number((detail.metrics as Record<string, number>).sharpe_ratio).toFixed(3)}</strong>
                  </div>
                )}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-3">
              <h3 className="font-medium text-gray-800">{t('component.backtest_overview.deploy.step2_title')}</h3>
              <div>
                <label className="block text-xs text-gray-600 mb-1">{t('component.backtest_overview.deploy.initial_capital')}</label>
                <input type="number" value={cash} onChange={e => setCash(e.target.value)}
                  className="input w-full" min={10000} max={1_000_000_000} step={10000} />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">{t('component.backtest_overview.deploy.risk_mode')}</label>
                <select value={riskMode} onChange={e => setRiskMode(e.target.value as typeof riskMode)}
                  className="input w-full">
                  <option value="conservative">{t('component.backtests.deploy_wizard.mode_conservative')}</option>
                  <option value="moderate">{t('component.backtests.deploy_wizard.mode_moderate')}</option>
                  <option value="aggressive">{t('component.backtests.deploy_wizard.mode_aggressive')}</option>
                </select>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg text-xs space-y-1 text-gray-600">
                <div className="font-medium text-gray-700 mb-1">{t('component.backtests.deploy_wizard.risk_params')}</div>
                {riskDetailItems.map((d, i) => <div key={i}>- {d}</div>)}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-3">
              <h3 className="font-medium text-gray-800">{t('component.backtest_overview.deploy.step3_title')}</h3>
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm space-y-1">
                <div>{t('component.backtest_overview.deploy.strategy')} <strong>{String(detail.strategy_id)}</strong></div>
                <div>{t('component.backtests.deploy_wizard.capital')} <strong>{Number(cash).toLocaleString()}</strong></div>
                <div>{t('component.backtest_overview.deploy.risk_mode')} <strong>{riskMode}</strong></div>
              </div>
              <div className="space-y-2">
                {[
                  { key: 'confirmBacktest', label: t('component.backtests.deploy_wizard.confirm_backtest_simple', { sharpe: Number((detail.metrics as Record<string, number>)?.sharpe_ratio ?? 0).toFixed(3) }) },
                  { key: 'understandPaper', label: t('component.backtests.deploy_wizard.confirm_paper') },
                  { key: 'reviewRisk', label: t('component.backtests.deploy_wizard.confirm_risk') },
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
            {step === 1 ? t('common.cancel') : t('component.backtest_overview.deploy.back')}
          </button>
          {step < 3 ? (
            <button onClick={() => setStep(s => s + 1)} className="btn-primary text-sm">
              {t('component.backtest_overview.deploy.next')}
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
              {deployMutation.isPending ? t('component.backtest_overview.deploy.deploying') : t('component.backtest_overview.deploy.confirm_deployment')}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

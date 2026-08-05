/**
 * Covariance matrix computation card.
 * Inputs: asset IDs, estimation method, window, halflife.
 */
import { useTranslation } from 'react-i18next'

interface CovarianceCardProps {
  assetIdsText: string
  onAssetIdsTextChange: (val: string) => void
  covMethod: 'historical' | 'ewma' | 'ledoit_wolf'
  onCovMethodChange: (val: 'historical' | 'ewma' | 'ledoit_wolf') => void
  covWindow: string
  onCovWindowChange: (val: string) => void
  covHalflife: string
  onCovHalflifeChange: (val: string) => void
  onCompute: () => void
  isPending: boolean
  error: Error | null
  covResult: Record<string, Record<string, number>> | null
}

export function CovarianceCard({
  assetIdsText, onAssetIdsTextChange,
  covMethod, onCovMethodChange,
  covWindow, onCovWindowChange,
  covHalflife, onCovHalflifeChange,
  onCompute, isPending, error, covResult,
}: CovarianceCardProps) {
  const { t } = useTranslation()
  return (
    <div className="bg-white rounded-xl shadow-sm border p-5 space-y-4">
      <h2 className="font-semibold text-gray-800">{t('component.optimize.covariance.title')}</h2>
      <div>
        <label className="text-xs text-gray-500 mb-1 block">{t('component.optimize.covariance.asset_ids')}</label>
        <input className="input w-full" value={assetIdsText}
          onChange={e => onAssetIdsTextChange(e.target.value)}
          placeholder="600519.SSE, 000858.SZSE, 601318.SSE" />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">{t('component.optimize.covariance.estimation_method')}</label>
          <select className="input w-full" value={covMethod} onChange={e => onCovMethodChange(e.target.value as any)}>
            <option value="historical">historical</option>
            <option value="ewma">ewma</option>
            <option value="ledoit_wolf">ledoit_wolf</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">{t('component.optimize.covariance.window_days')}</label>
          <input type="number" className="input w-full" value={covWindow}
            onChange={e => onCovWindowChange(e.target.value)} min={20} />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">{t('component.optimize.covariance.halflife_days')}</label>
          <input type="number" className="input w-full" value={covHalflife}
            onChange={e => onCovHalflifeChange(e.target.value)} min={5} />
        </div>
      </div>
      <button className="btn-primary" onClick={onCompute}
        disabled={isPending || assetIdsText.split(',').filter(Boolean).length < 2}>
        {isPending ? t('component.optimize.covariance.computing') : t('component.optimize.covariance.compute')}
      </button>
      {error && (
        <div className="text-red-600 text-sm">{String(error)}</div>
      )}
      {covResult && (
        <div className="text-sm text-green-700">
          {t('component.optimize.covariance.computed', { count: Object.keys(covResult).length })}
        </div>
      )}
    </div>
  )
}

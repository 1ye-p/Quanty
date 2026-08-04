/**
 * Walk-forward fold metrics grid.
 * Displays Sharpe ratio and return for each fold.
 */
import { useTranslation } from 'react-i18next'

export function FoldMetricsCard({ folds }: { folds: Record<string, unknown>[] }) {
  const { t } = useTranslation()
  if (!folds || folds.length === 0) return null
  return (
    <div className="card">
      <h3 className="font-semibold text-gray-800 mb-3">{t('component.overfitting.section.wf_fold_metrics')}</h3>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {folds.map((fold, i) => {
          const metrics = fold.metrics_json as Record<string, number> | null
          const sharpe = metrics?.sharpe ?? 0
          const ret = metrics?.total_return ?? 0
          return (
            <div key={i} className={`text-center p-3 rounded-lg ${sharpe > 0 ? 'bg-green-50' : 'bg-red-50'}`}>
              <div className="text-xs text-gray-500 mb-1">{t('component.overfitting.label.fold', { index: i + 1 })}</div>
              <div className={`text-lg font-bold ${sharpe > 0 ? 'text-green-700' : 'text-red-700'}`}>
                {sharpe.toFixed(2)}
              </div>
              <div className="text-xs text-gray-400">{t('component.overfitting.label.sharpe')}</div>
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

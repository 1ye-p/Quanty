/**
 * Risk budget configuration for risk parity optimization.
 * Displays current risk allocation if available.
 */
import { useTranslation } from 'react-i18next'

interface RiskBudgetTabProps {
  resultWeights?: Record<string, number>
  covariance?: Record<string, Record<string, number>> | null
}

export function RiskBudgetTab({ resultWeights, covariance }: RiskBudgetTabProps) {
  const { t } = useTranslation()
  const assets = resultWeights ? Object.keys(resultWeights) : covariance ? Object.keys(covariance) : []

  if (assets.length === 0) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-3">{t('component.optimize.risk_budget.title')}</h3>
        <p className="text-sm text-gray-400">
          {t('component.optimize.risk_budget.empty_hint')}
        </p>
      </div>
    )
  }

  // If we have results, show risk contribution estimate
  if (resultWeights && covariance) {
    const totalWeight = Object.values(resultWeights).reduce((a, b) => a + b, 0)
    if (totalWeight === 0) return null

    // Full marginal risk contribution using covariance matrix
    // MRC_i = w_i * (Σw)_i / sqrt(w'Σw)
    const wVec = assets.map(a => resultWeights[a] ?? 0)
    // Assumes covariance matrix is symmetric: cov[a][b] == cov[b][a]
    const sigmaMatrix = assets.map(a1 => assets.map(a2 => covariance[a1]?.[a2] ?? 0))

    // Σw: matrix-vector multiply
    const sigmaW = sigmaMatrix.map(row => row.reduce((sum, val, j) => sum + val * wVec[j], 0))

    // w'Σw: dot product of w and Σw
    const wSigmaW = wVec.reduce((sum, wi, i) => sum + wi * sigmaW[i], 0)
    const portfolioVol = Math.sqrt(Math.max(0, wSigmaW))

    // Marginal risk contribution: w_i * (Σw)_i / portfolio_vol
    const contributions = assets.map((asset, i) => {
      const w = wVec[i]
      const mrc = portfolioVol > 0 ? (w * sigmaW[i]) / portfolioVol : 0
      return { asset, weight: w, riskContrib: mrc }
    })

    const totalRisk = contributions.reduce((a, b) => a + b.riskContrib, 0)

    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-3">{t('component.optimize.risk_budget.risk_contribution')}</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="py-1">{t('component.optimize.shared.asset')}</th>
              <th className="py-1 text-right">{t('component.optimize.shared.weight')}</th>
              <th className="py-1 text-right">{t('component.optimize.risk_budget.col_risk_contrib')}</th>
              <th className="py-1 text-right">{t('component.optimize.risk_budget.col_pct_total')}</th>
            </tr>
          </thead>
          <tbody>
            {contributions
              .sort((a, b) => b.riskContrib - a.riskContrib)
              .map(c => (
                <tr key={c.asset} className="border-b border-gray-100">
                  <td className="py-1 font-mono text-xs">{c.asset}</td>
                  <td className="py-1 text-right">{(c.weight * 100).toFixed(2)}%</td>
                  <td className="py-1 text-right">{c.riskContrib.toFixed(4)}</td>
                  <td className="py-1 text-right">
                    {totalRisk > 0 ? `${((c.riskContrib / totalRisk) * 100).toFixed(1)}%` : '--'}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className="card">
      <h3 className="font-semibold text-gray-800 mb-3">{t('component.optimize.risk_budget.title')}</h3>
      <p className="text-sm text-gray-400">
        {t('component.optimize.risk_budget.empty_run_hint')}
      </p>
      <div className="mt-3">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="py-1">{t('component.optimize.shared.asset')}</th>
              <th className="py-1 text-right">{t('component.optimize.risk_budget.col_variance')}</th>
            </tr>
          </thead>
          <tbody>
            {assets.map(asset => (
              <tr key={asset} className="border-b border-gray-100">
                <td className="py-1 font-mono text-xs">{asset}</td>
                <td className="py-1 text-right font-mono text-xs">
                  {covariance?.[asset]?.[asset]?.toFixed(6) ?? '--'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

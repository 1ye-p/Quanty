/**
 * Risk budget configuration for risk parity optimization.
 * Displays current risk allocation if available.
 */

interface RiskBudgetTabProps {
  resultWeights?: Record<string, number>
  covariance?: Record<string, Record<string, number>> | null
}

export function RiskBudgetTab({ resultWeights, covariance }: RiskBudgetTabProps) {
  const assets = resultWeights ? Object.keys(resultWeights) : covariance ? Object.keys(covariance) : []

  if (assets.length === 0) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-3">Risk Budget</h3>
        <p className="text-sm text-gray-400">
          Compute covariance first, then run risk_parity optimization to see risk contribution breakdown.
        </p>
      </div>
    )
  }

  // If we have results, show risk contribution estimate
  if (resultWeights && covariance) {
    // Simple marginal risk contribution estimate
    const totalWeight = Object.values(resultWeights).reduce((a, b) => a + b, 0)
    if (totalWeight === 0) return null

    // Simplified risk contribution: weight * volatility (diagonal only)
    // Full marginal risk = w_i * (Σw)_i / sqrt(w'Σw), but we approximate
    // with per-asset volatility for the UI display
    const contributions = assets.map(asset => {
      const w = resultWeights[asset] ?? 0
      const variance = covariance[asset]?.[asset] ?? 0
      const riskContrib = w * Math.sqrt(variance)
      return { asset, weight: w, riskContrib }
    })

    const totalRisk = contributions.reduce((a, b) => a + b.riskContrib, 0)

    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-3">Risk Contribution</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="py-1">Asset</th>
              <th className="py-1 text-right">Weight</th>
              <th className="py-1 text-right">Risk Contrib</th>
              <th className="py-1 text-right">% of Total</th>
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
      <h3 className="font-semibold text-gray-800 mb-3">Risk Budget</h3>
      <p className="text-sm text-gray-400">
        Run risk_parity optimization to see risk contribution breakdown.
      </p>
      <div className="mt-3">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="py-1">Asset</th>
              <th className="py-1 text-right">Variance</th>
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

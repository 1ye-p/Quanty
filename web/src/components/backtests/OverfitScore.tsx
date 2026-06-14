/**
 * Overfit score progress bar with risk label.
 */

export function OverfitScore({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = score > 0.7 ? 'bg-red-500' : score > 0.4 ? 'bg-yellow-500' : 'bg-green-500'
  const label = score > 0.7 ? 'Significant overfitting detected' : score > 0.4 ? 'Mild overfitting' : 'Low overfit risk'
  const badgeClass = score > 0.7 ? 'bg-red-100 text-red-800' : score > 0.4 ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700">Overfit Score</span>
        <span className={`badge ${badgeClass}`}>{pct}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <div className="text-xs text-gray-400 mt-1">{label}</div>
    </div>
  )
}

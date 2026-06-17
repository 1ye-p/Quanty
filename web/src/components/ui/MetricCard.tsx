/** Reusable metric card for dashboard displays. */
export function MetricCard({ label, value, sub, warn = false, good = false }: {
  label: string; value: string | number; sub?: string; warn?: boolean; good?: boolean
}) {
  const valueClass = warn ? 'text-red-600' : good ? 'text-green-600' : 'text-brand-600'
  const borderClass = warn ? 'border-l-4 border-red-400' : good ? 'border-l-4 border-green-400' : ''
  return (
    <div className={`card text-center py-4 ${borderClass}`}>
      <div className={`text-xl font-bold ${valueClass}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  )
}

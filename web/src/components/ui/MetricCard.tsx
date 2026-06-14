/** Reusable metric card for dashboard displays. */
export function MetricCard({ label, value, sub, warn = false }: {
  label: string; value: string | number; sub?: string; warn?: boolean
}) {
  return (
    <div className={`card text-center py-4 ${warn ? 'border-l-4 border-red-400' : ''}`}>
      <div className={`text-xl font-bold ${warn ? 'text-red-600' : 'text-brand-600'}`}>{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  )
}

/**
 * ML predictions modal content.
 * Displays real-time model predictions as a ranked table.
 */
import { useQuery } from '@tanstack/react-query'
import { mlApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'

interface PredictionsTabProps {
  runId: string
}

export function PredictionsTab({ runId }: PredictionsTabProps) {
  const { data: predictResult, isFetching } = useQuery({
    queryKey: extendedQueryKeys.ml.predict(runId),
    queryFn: () => mlApi.predict({ model_version: runId, top_n: 30 }),
    staleTime: 60_000,
  })

  if (isFetching) {
    return (
      <div className="flex items-center justify-center py-8 text-gray-500">
        <div className="animate-spin w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full mr-2" />
        Loading model...
      </div>
    )
  }

  if (!predictResult?.predictions?.length) {
    return <div className="text-center text-gray-400 py-8">No prediction data</div>
  }

  return (
    <div>
      <div className="text-xs text-gray-500 mb-3">
        Total {predictResult.total_assets} assets, showing Top-{predictResult.top_n}
        {predictResult.date && <span className="ml-2">Date: {predictResult.date}</span>}
        {predictResult.trainer_name && <span className="ml-2">Trainer: {predictResult.trainer_name}</span>}
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 border-b">
            <th className="py-1.5 pr-3 w-12">#</th>
            <th className="py-1.5 pr-3">Asset</th>
            <th className="py-1.5 text-right">Predicted Return</th>
          </tr>
        </thead>
        <tbody>
          {predictResult.predictions.map((p, i) => (
            <tr key={p.asset_id}
              className={`border-b border-gray-100 ${i < 3 ? 'bg-green-50' : i >= predictResult.predictions.length - 3 ? 'bg-red-50' : ''}`}>
              <td className="py-1.5 pr-3 font-mono text-gray-400">{p.rank}</td>
              <td className="py-1.5 pr-3 font-mono font-medium">{p.asset_id}</td>
              <td className={`py-1.5 text-right font-mono ${
                p.prediction > 0 ? 'text-green-600' : p.prediction < 0 ? 'text-red-600' : 'text-gray-400'
              }`}>
                {(p.prediction * 100).toFixed(2)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

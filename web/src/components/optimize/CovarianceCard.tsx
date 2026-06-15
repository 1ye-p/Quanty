/**
 * Covariance matrix computation card.
 * Inputs: asset IDs, estimation method, window, halflife.
 */

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
  return (
    <div className="bg-white rounded-xl shadow-sm border p-5 space-y-4">
      <h2 className="font-semibold text-gray-800">协方差计算</h2>
      <div>
        <label className="text-xs text-gray-500 mb-1 block">资产 ID（逗号分隔）</label>
        <input className="input w-full" value={assetIdsText}
          onChange={e => onAssetIdsTextChange(e.target.value)}
          placeholder="600519.SSE, 000858.SZSE, 601318.SSE" />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">估计方法</label>
          <select className="input w-full" value={covMethod} onChange={e => onCovMethodChange(e.target.value as any)}>
            <option value="historical">historical</option>
            <option value="ewma">ewma</option>
            <option value="ledoit_wolf">ledoit_wolf</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">窗口（天）</label>
          <input type="number" className="input w-full" value={covWindow}
            onChange={e => onCovWindowChange(e.target.value)} min={20} />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">半衰期（天）</label>
          <input type="number" className="input w-full" value={covHalflife}
            onChange={e => onCovHalflifeChange(e.target.value)} min={5} />
        </div>
      </div>
      <button className="btn-primary" onClick={onCompute}
        disabled={isPending || assetIdsText.split(',').filter(Boolean).length < 2}>
        {isPending ? '计算中...' : '计算协方差'}
      </button>
      {error && (
        <div className="text-red-600 text-sm">{String(error)}</div>
      )}
      {covResult && (
        <div className="text-sm text-green-700">
          协方差矩阵已计算：{Object.keys(covResult).length} 个资产
        </div>
      )}
    </div>
  )
}

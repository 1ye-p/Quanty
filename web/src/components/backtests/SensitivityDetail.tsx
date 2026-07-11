interface SensitivityDetailProps {
  paramX: string
  paramXValue: string
  paramY: string
  paramYValue: string
  metrics: Record<string, number>
  onRunBacktest?: (params: Record<string, any>) => void
  onClose: () => void
}

export function SensitivityDetail({ paramX, paramXValue, paramY, paramYValue, metrics, onRunBacktest, onClose }: SensitivityDetailProps) {
  return (
    <div className="card p-4 space-y-3">
      <div className="flex justify-between items-center">
        <h4 className="font-semibold text-sm">参数组合详情</h4>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div><span className="text-gray-500">{paramX}:</span> {paramXValue}</div>
        <div><span className="text-gray-500">{paramY}:</span> {paramYValue}</div>
      </div>
      <div className="space-y-1">
        {Object.entries(metrics).map(([key, val]) => (
          <div key={key} className="flex justify-between text-sm">
            <span className="text-gray-600">{key}</span>
            <span className="font-mono">{typeof val === 'number' ? val.toFixed(4) : val}</span>
          </div>
        ))}
      </div>
      {onRunBacktest && (
        <button
          onClick={() => onRunBacktest({ [paramX]: paramXValue, [paramY]: paramYValue })}
          className="btn-primary text-sm w-full"
        >
          用此参数运行回测
        </button>
      )}
    </div>
  )
}

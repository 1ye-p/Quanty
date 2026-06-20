/**
 * Black-Litterman views panel.
 *
 * Allows the user to specify investor views (absolute or relative)
 * and the tau uncertainty parameter for the Black-Litterman model.
 */
import type { ViewSpec } from '@/lib/api'

interface BlackLittermanTabProps {
  assets: string[]
  views: ViewSpec[]
  onViewsChange: (views: ViewSpec[]) => void
  tau: number
  onTauChange: (tau: number) => void
}

export function BlackLittermanTab({
  assets,
  views,
  onViewsChange,
  tau,
  onTauChange,
}: BlackLittermanTabProps) {
  const addView = () => {
    onViewsChange([
      ...views,
      { asset: assets[0] ?? '', expected_return: 0, confidence: 0.5 },
    ])
  }

  const removeView = (idx: number) => {
    onViewsChange(views.filter((_, i) => i !== idx))
  }

  const updateView = (idx: number, patch: Partial<ViewSpec>) => {
    onViewsChange(views.map((v, i) => (i === idx ? { ...v, ...patch } : v)))
  }

  const isRelative = (v: ViewSpec) => v.against !== undefined && v.against !== ''

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4 space-y-4">
      <h3 className="font-semibold text-gray-800">Black-Litterman 观点</h3>

      {/* Tau slider */}
      <div className="flex items-center gap-4">
        <label className="text-xs text-gray-500 whitespace-nowrap">
          tau (不确定性系数)
        </label>
        <input
          type="range"
          min={0.001}
          max={0.5}
          step={0.001}
          value={tau}
          onChange={e => onTauChange(Number(e.target.value))}
          className="flex-1"
        />
        <input
          type="number"
          min={0.001}
          max={0.5}
          step={0.001}
          value={tau}
          onChange={e => {
            const v = Number(e.target.value)
            if (!isNaN(v) && v > 0) onTauChange(v)
          }}
          className="input w-20 text-right text-xs"
        />
      </div>

      {/* Views table */}
      {assets.length === 0 ? (
        <p className="text-sm text-gray-500">
          请先完成协方差矩阵计算以获取资产列表。
        </p>
      ) : (
        <>
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="table-th text-left">资产</th>
                  <th className="table-th text-left">类型</th>
                  <th className="table-th text-left">Against</th>
                  <th className="table-th text-right">预期收益 (%)</th>
                  <th className="table-th text-right">置信度 (%)</th>
                  <th className="table-th w-10" />
                </tr>
              </thead>
              <tbody>
                {views.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-3 py-4 text-center text-gray-400 text-xs">
                      暂无观点，点击下方按钮添加
                    </td>
                  </tr>
                ) : (
                  views.map((v, idx) => (
                    <tr key={idx} className="border-t hover:bg-gray-50">
                      {/* Asset */}
                      <td className="px-2 py-1.5">
                        <select
                          value={v.asset}
                          onChange={e => updateView(idx, { asset: e.target.value })}
                          className="input w-full text-xs"
                        >
                          {assets.map(a => (
                            <option key={a} value={a}>{a}</option>
                          ))}
                        </select>
                      </td>

                      {/* Type */}
                      <td className="px-2 py-1.5">
                        <select
                          value={isRelative(v) ? 'relative' : 'absolute'}
                          onChange={e => {
                            if (e.target.value === 'absolute') {
                              updateView(idx, { against: undefined })
                            } else {
                              updateView(idx, { against: assets[1] ?? assets[0] ?? '' })
                            }
                          }}
                          className="input w-full text-xs"
                        >
                          <option value="absolute">绝对</option>
                          <option value="relative">相对</option>
                        </select>
                      </td>

                      {/* Against */}
                      <td className="px-2 py-1.5">
                        {isRelative(v) ? (
                          <select
                            value={v.against}
                            onChange={e => updateView(idx, { against: e.target.value })}
                            className="input w-full text-xs"
                          >
                            {assets
                              .filter(a => a !== v.asset)
                              .map(a => (
                                <option key={a} value={a}>{a}</option>
                              ))}
                          </select>
                        ) : (
                          <span className="text-gray-300 text-xs">--</span>
                        )}
                      </td>

                      {/* Expected return */}
                      <td className="px-2 py-1.5">
                        <input
                          type="number"
                          step={0.1}
                          value={v.expected_return * 100}
                          onChange={e => {
                            const val = Number(e.target.value)
                            if (!isNaN(val)) updateView(idx, { expected_return: val / 100 })
                          }}
                          className="w-full text-right border rounded px-2 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500"
                        />
                      </td>

                      {/* Confidence */}
                      <td className="px-2 py-1.5">
                        <div className="flex items-center gap-1">
                          <input
                            type="range"
                            min={0}
                            max={100}
                            value={Math.round(v.confidence * 100)}
                            onChange={e => updateView(idx, { confidence: Number(e.target.value) / 100 })}
                            className="flex-1"
                          />
                          <span className="text-xs text-gray-500 w-8 text-right">
                            {Math.round(v.confidence * 100)}
                          </span>
                        </div>
                      </td>

                      {/* Remove */}
                      <td className="px-2 py-1.5 text-center">
                        <button
                          type="button"
                          onClick={() => removeView(idx)}
                          className="text-red-400 hover:text-red-600 text-xs"
                          title="删除"
                        >
                          x
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <button
            type="button"
            onClick={addView}
            className="text-xs text-brand-600 hover:underline"
          >
            + 添加观点
          </button>
        </>
      )}

      {/* Summary */}
      {views.length > 0 && (
        <div className="text-xs text-gray-500 space-y-1 pt-2 border-t">
          <p>
            共 {views.length} 条观点：
            {views.filter(v => !isRelative(v)).length} 条绝对，
            {views.filter(v => isRelative(v)).length} 条相对。
          </p>
          <p>
            平均置信度：{Math.round((views.reduce((s, v) => s + v.confidence, 0) / views.length) * 100)}%
          </p>
        </div>
      )}
    </div>
  )
}

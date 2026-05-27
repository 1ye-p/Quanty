import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { optimizeApi, mlApi } from '@/lib/api'
import type { OptimizeResult } from '@/lib/api'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'

const COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
]

export function OptimizePage() {
  const navigate = useNavigate()

  // Covariance inputs
  const [assetIdsText, setAssetIdsText] = useState('')
  const [covMethod, setCovMethod] = useState<'historical' | 'ewma' | 'ledoit_wolf'>('historical')
  const [covWindow, setCovWindow] = useState('252')
  const [covHalflife, setCovHalflife] = useState('63')

  // Optimizer inputs
  const [optimizer, setOptimizer] = useState<'mean_variance' | 'risk_parity' | 'cost_aware'>('mean_variance')
  const [longOnly, setLongOnly] = useState(true)
  const [riskFreeRate, setRiskFreeRate] = useState('0')
  const [costRate, setCostRate] = useState('0.001')
  const [turnoverPenalty, setTurnoverPenalty] = useState('0.0005')

  // Expected returns (manual input per asset)
  const [returnsText, setReturnsText] = useState('')
  const [expectedReturnsMap, setExpectedReturnsMap] = useState<Record<string, number>>({})

  // Results
  const [covResult, setCovResult] = useState<Record<string, Record<string, number>> | null>(null)
  const [optResult, setOptResult] = useState<OptimizeResult | null>(null)

  const covMutation = useMutation({
    mutationFn: optimizeApi.covariance,
    onSuccess: (data) => {
      setCovResult(data.covariance)
      // Initialize expected returns map: keep existing values, default new assets to 0
      const assets = Object.keys(data.covariance)
      setExpectedReturnsMap(prev => {
        const next: Record<string, number> = {}
        for (const a of assets) {
          next[a] = prev[a] ?? 0
        }
        return next
      })
    },
  })

  const optMutation = useMutation({
    mutationFn: optimizeApi.optimize,
    onSuccess: (data) => setOptResult(data),
  })

  // Fetch ML predictions for the current covariance assets (lazy — only when covResult exists)
  const covAssets = covResult ? Object.keys(covResult) : []
  const { data: mlPredictions, isFetching: mlFetching } = useQuery({
    queryKey: ['ml', 'predictions', covAssets.join(',')],
    queryFn: () => mlApi.predictions(covAssets),
    enabled: covAssets.length > 0,
    staleTime: 60_000,
  })

  const handleImportMlPredictions = () => {
    if (!mlPredictions?.predictions || !Object.keys(mlPredictions.predictions).length) return
    setExpectedReturnsMap(prev => {
      const next = { ...prev }
      for (const [asset, pred] of Object.entries(mlPredictions.predictions)) {
        if (asset in next) next[asset] = pred
      }
      return next
    })
  }

  const handleComputeCov = () => {
    const assetIds = assetIdsText.split(',').map(s => s.trim()).filter(Boolean)
    if (assetIds.length < 2) return
    covMutation.mutate({
      asset_ids: assetIds,
      method: covMethod,
      window: Number(covWindow) || 252,
      halflife: Number(covHalflife) || 63,
    })
  }

  const handleOptimize = () => {
    if (!covResult) return
    // Parse expected returns
    const assets = Object.keys(covResult)
    // Use expectedReturnsMap directly (values already in decimal form)
    const returns: Record<string, number> = { ...expectedReturnsMap }
    for (const a of assets) {
      if (!(a in returns)) returns[a] = 0
    }

    optMutation.mutate({
      expected_returns: returns,
      covariance: covResult,
      optimizer,
      long_only: longOnly,
      risk_free_rate: Number(riskFreeRate) || 0,
      cost_rate: Number(costRate) || 0.001,
      turnover_penalty: Number(turnoverPenalty) || 0.0005,
    })
  }

  const pieData = optResult
    ? Object.entries(optResult.weights)
        .filter(([, w]) => w > 0.001)
        .map(([asset, weight]) => ({ name: asset, value: Math.round(weight * 10000) / 100 }))
    : []

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">组合优化</h1>

      {/* Covariance Card */}
      <div className="bg-white rounded-xl shadow-sm border p-5 space-y-4">
        <h2 className="font-semibold text-gray-800">协方差计算</h2>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">资产 ID（逗号分隔）</label>
          <input className="input w-full" value={assetIdsText}
            onChange={e => setAssetIdsText(e.target.value)}
            placeholder="600519.SSE, 000858.SZSE, 601318.SSE" />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">估计方法</label>
            <select className="input w-full" value={covMethod} onChange={e => setCovMethod(e.target.value as any)}>
              <option value="historical">historical</option>
              <option value="ewma">ewma</option>
              <option value="ledoit_wolf">ledoit_wolf</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">窗口（天）</label>
            <input type="number" className="input w-full" value={covWindow}
              onChange={e => setCovWindow(e.target.value)} min={20} />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">半衰期（天）</label>
            <input type="number" className="input w-full" value={covHalflife}
              onChange={e => setCovHalflife(e.target.value)} min={5} />
          </div>
        </div>
        <button className="btn-primary" onClick={handleComputeCov}
          disabled={covMutation.isPending || assetIdsText.split(',').filter(Boolean).length < 2}>
          {covMutation.isPending ? '计算中...' : '计算协方差'}
        </button>
        {covMutation.isError && (
          <div className="text-red-600 text-sm">{String(covMutation.error)}</div>
        )}
        {covResult && (
          <div className="text-sm text-green-700">
            协方差矩阵已计算：{Object.keys(covResult).length} 个资产
          </div>
        )}
      </div>

      {/* Optimizer Config Card */}
      <div className="bg-white rounded-xl shadow-sm border p-5 space-y-4">
        <h2 className="font-semibold text-gray-800">优化器配置</h2>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">优化器类型</label>
            <select className="input w-full" value={optimizer} onChange={e => setOptimizer(e.target.value as any)}>
              <option value="mean_variance">mean_variance — 均值方差</option>
              <option value="risk_parity">risk_parity — 风险平价</option>
              <option value="cost_aware">cost_aware — 成本感知</option>
            </select>
          </div>
          <div className="flex items-end gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={longOnly} onChange={e => setLongOnly(e.target.checked)} />
              仅做多 (Long Only)
            </label>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">无风险利率</label>
            <input type="number" className="input w-full" value={riskFreeRate}
              onChange={e => setRiskFreeRate(e.target.value)} step={0.001} />
          </div>
          {optimizer === 'cost_aware' && (
            <>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">交易成本率</label>
                <input type="number" className="input w-full" value={costRate}
                  onChange={e => setCostRate(e.target.value)} step={0.0001} min={0} />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">换手惩罚</label>
                <input type="number" className="input w-full" value={turnoverPenalty}
                  onChange={e => setTurnoverPenalty(e.target.value)} step={0.0001} min={0} />
              </div>
            </>
          )}
        </div>
        {/* 预期收益输入 — 表格模式（协方差计算后显示） */}
        {covResult && Object.keys(expectedReturnsMap).length > 0 ? (
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700">预期年化收益率（%）</label>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    const input = prompt('批量填充预期收益率（%）:', '10')
                    if (input === null) return
                    const val = Number(input)
                    if (!isNaN(val)) {
                      setExpectedReturnsMap(prev =>
                        Object.fromEntries(Object.keys(prev).map(k => [k, val / 100]))
                      )
                    }
                  }}
                  className="text-xs text-brand-600 hover:underline"
                >
                  批量填充
                </button>
                <button
                  type="button"
                  onClick={handleImportMlPredictions}
                  disabled={mlFetching || !mlPredictions?.predictions || !Object.keys(mlPredictions.predictions).length}
                  title={mlPredictions?.date ? `来自 ${mlPredictions.date}` : '无 ML 预测数据'}
                  className="text-xs text-purple-600 hover:underline disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {mlFetching ? '加载…' : '导入 ML 预测'}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setExpectedReturnsMap(prev =>
                      Object.fromEntries(Object.keys(prev).map(k => [k, 0]))
                    )
                  }
                  className="text-xs text-gray-400 hover:text-gray-600"
                >
                  清零
                </button>
              </div>
            </div>
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="table-th text-left">资产代码</th>
                    <th className="table-th text-right">预期年化收益率 (%)</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(expectedReturnsMap).map(([asset, ret]) => (
                    <tr key={asset} className="border-t hover:bg-gray-50">
                      <td className="px-3 py-1.5 font-mono text-xs text-gray-700">{asset}</td>
                      <td className="px-3 py-1.5">
                        <input
                          type="number"
                          step={0.1}
                          value={ret * 100}
                          onChange={e => {
                            const val = Number(e.target.value)
                            if (isNaN(val)) return
                            setExpectedReturnsMap(prev => ({ ...prev, [asset]: val / 100 }))
                          }}
                          className="w-full text-right border rounded px-2 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500"
                          placeholder="0"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-gray-400 mt-1">
              risk_parity 优化器不使用预期收益，均值方差优化器需要设置。
            </p>
            {/* 高级文本模式（折叠） */}
            <details className="mt-2">
              <summary className="text-xs text-gray-400 cursor-pointer">高级：文本模式输入</summary>
              <textarea
                rows={4}
                value={returnsText}
                onChange={e => {
                  setReturnsText(e.target.value)
                  // Sync to map
                  const map: Record<string, number> = {}
                  for (const line of e.target.value.split('\n').filter(Boolean)) {
                    const [a, v] = line.split(',').map(s => s.trim())
                    if (a && v) map[a] = Number(v)
                  }
                  setExpectedReturnsMap(prev => {
                    const next: Record<string, number> = {}
                    for (const a of Object.keys(prev)) {
                      next[a] = map[a] !== undefined ? map[a] : prev[a]
                    }
                    return next
                  })
                }}
                placeholder="asset_id, expected_return (小数形式，如 0.10 表示10%)"
                className="mt-1 w-full font-mono text-xs border rounded p-2 focus:outline-none"
              />
            </details>
          </div>
        ) : (
          /* 协方差未计算时：提示先计算协方差 */
          <div className="p-3 bg-gray-50 border rounded-lg text-sm text-gray-500">
            请先完成上方的协方差矩阵计算，资产列表将自动填入预期收益表格。
          </div>
        )}
        <button className="btn-primary" onClick={handleOptimize}
          disabled={optMutation.isPending || !covResult}>
          {optMutation.isPending ? '优化中...' : '运行优化'}
        </button>
        {optMutation.isError && (
          <div className="text-red-600 text-sm">{String(optMutation.error)}</div>
        )}
      </div>

      {/* Results Card */}
      {optResult && (
        <div className="bg-white rounded-xl shadow-sm border p-5 space-y-4">
          <h2 className="font-semibold text-gray-800">优化结果</h2>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="bg-blue-50 rounded-lg p-3">
              <div className="text-xs text-gray-500">预期收益</div>
              <div className="text-lg font-bold text-blue-700">
                {(optResult.expected_return * 100).toFixed(2)}%
              </div>
            </div>
            <div className="bg-green-50 rounded-lg p-3">
              <div className="text-xs text-gray-500">预期波动率</div>
              <div className="text-lg font-bold text-green-700">
                {(optResult.expected_volatility * 100).toFixed(2)}%
              </div>
            </div>
            <div className="bg-purple-50 rounded-lg p-3">
              <div className="text-xs text-gray-500">Sharpe Ratio</div>
              <div className="text-lg font-bold text-purple-700">
                {optResult.sharpe_ratio.toFixed(3)}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6">
            {/* Weights Table */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">权重分配</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b">
                    <th className="py-1">资产</th>
                    <th className="py-1 text-right">权重</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(optResult.weights)
                    .sort(([, a], [, b]) => b - a)
                    .map(([asset, weight]) => (
                      <tr key={asset} className="border-b border-gray-100">
                        <td className="py-1 font-mono text-xs">{asset}</td>
                        <td className="py-1 text-right">{(weight * 100).toFixed(2)}%</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>

            {/* Pie Chart */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">权重分布</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name"
                      cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name} ${value}%`}>
                      {pieData.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: number) => `${v}%`} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <button
            className="btn-secondary text-sm w-full mt-2"
            onClick={() => {
              const weights = optResult.weights as Record<string, number>
              navigate('/strategies', {
                state: {
                  openBacktest: true,
                  prefill: {
                    strategy_id: `opt_${optimizer}_${Date.now().toString(36)}`,
                    config: JSON.stringify({
                      strategy_type: 'CustomWeightStrategy',
                      custom_weights: weights,
                    }, null, 2),
                  },
                },
              })
            }}
          >
            → 用这组权重运行回测
          </button>
        </div>
      )}
    </div>
  )
}

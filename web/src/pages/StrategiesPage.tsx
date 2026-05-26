import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useLocation } from 'react-router-dom'
import { strategiesApi, backtestsApi, datasetsApi, riskApi, mlApi } from '@/lib/api'
import { queryKeys, extendedQueryKeys } from '@/lib/queryKeys'
import Editor from '@monaco-editor/react'
import { toast } from 'sonner'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'

const DEFAULT_CONFIG = JSON.stringify({
  strategy_id: "my_strategy",
  universe: { exchange: ["SSE", "SZSE"], min_liquidity: 1000000 },
  rebalance_frequency: "1d",
  risk_limits: { max_position_pct: 0.10, max_gross_leverage: 1.0 },
  factors: ["ret_20d", "vol_20d"],
  sizer: "equal_weight"
}, null, 2)

function StrategyBuilder({
  initialConfig,
  onChange,
}: {
  initialConfig: string
  onChange: (json: string) => void
}) {
  const parsed = useMemo(() => {
    try { return JSON.parse(initialConfig) } catch { return {} }
  }, [initialConfig])

  const [strategyType, setStrategyType] = useState(parsed.strategy_type ?? 'StaticTopN')
  const [factorsText, setFactorsText] = useState<string>((parsed.factors ?? ['ret_20d', 'vol_20d']).join(', '))
  const [topN, setTopN] = useState(String(parsed.top_n ?? 10))
  const [rebalance, setRebalance] = useState(parsed.rebalance_frequency ?? '1d')
  const [sizer, setSizer] = useState(parsed.sizer ?? 'equal_weight')
  const [sizerParams, setSizerParams] = useState<Record<string, string>>(parsed.sizer_params ?? {})
  const [selectedPolicies, setSelectedPolicies] = useState<string[]>(
    parsed.risk_policies ?? (parsed.risk_limits?.max_position_pct ? ['position_limit'] : [])
  )
  const [policyParams, setPolicyParams] = useState<Record<string, Record<string, string>>>(
    parsed.risk_policy_params ?? {}
  )
  const [maxPositionPct, setMaxPositionPct] = useState(String(parsed.risk_limits?.max_position_pct ?? 0.10))
  const [maxLeverage, setMaxLeverage] = useState(String(parsed.risk_limits?.max_gross_leverage ?? 1.0))
  // MarketNeutral params
  const [shortN, setShortN] = useState(String(parsed.short_n ?? 10))
  // SectorRotation params
  const [topSectors, setTopSectors] = useState(String(parsed.top_sectors ?? 3))
  const [topNPerSector, setTopNPerSector] = useState(String(parsed.top_n_per_sector ?? 3))
  // Combo params
  const [comboMethod, setComboMethod] = useState(parsed.combo_method ?? 'equal_weight')
  const [subStrategyConfigs, setSubStrategyConfigs] = useState<string>(
    JSON.stringify(parsed.sub_strategy_configs ?? [], null, 2)
  )
  // Universe params
  const [universeId, setUniverseId] = useState(parsed.universe_id ?? 'all')
  const [customAssets, setCustomAssets] = useState('')
  const [quickStopLoss, setQuickStopLoss] = useState(
    parsed.risk_policy_params?.stop_loss?.stop_loss_pct != null
      ? String(parsed.risk_policy_params.stop_loss.stop_loss_pct * 100)
      : ''
  )
  const [quickDrawdownBreaker, setQuickDrawdownBreaker] = useState(
    parsed.risk_policy_params?.drawdown_breaker?.max_drawdown_pct != null
      ? String(parsed.risk_policy_params.drawdown_breaker.max_drawdown_pct * 100)
      : ''
  )

  const { data: policies } = useQuery({
    queryKey: extendedQueryKeys.risk.policies(),
    queryFn: () => riskApi.policies(),
  })

  const { data: sizers } = useQuery({
    queryKey: extendedQueryKeys.risk.sizers(),
    queryFn: () => riskApi.sizers(),
  })

  const { data: universes } = useQuery({
    queryKey: ['datasets', 'universes'],
    queryFn: datasetsApi.universes,
    staleTime: 300_000,
  })

  // Generate JSON config whenever form state changes
  useEffect(() => {
    const factors = factorsText.split(',').map(f => f.trim()).filter(Boolean)
    const config: Record<string, unknown> = {
      strategy_id: parsed.strategy_id ?? 'my_strategy',
      strategy_type: strategyType,
      universe_id: universeId === 'custom' ? 'all' : universeId,
      rebalance_frequency: rebalance,
      top_n: Number(topN) || 10,
      factors,
      sizer,
    }
    if (strategyType === 'MarketNeutral') {
      config.short_n = Number(shortN) || 10
    }
    if (strategyType === 'SectorRotation') {
      config.top_sectors = Number(topSectors) || 3
      config.top_n_per_sector = Number(topNPerSector) || 3
    }
    if (strategyType === 'Combo') {
      config.combo_method = comboMethod
      try { config.sub_strategy_configs = JSON.parse(subStrategyConfigs) } catch { config.sub_strategy_configs = [] }
    }
    if (Object.keys(sizerParams).length > 0) {
      config.sizer_params = sizerParams
    }
    config.risk_limits = {
      max_position_pct: Number(maxPositionPct) || 0.10,
      max_gross_leverage: Number(maxLeverage) || 1.0,
    }
    if (selectedPolicies.length > 0) {
      config.risk_policies = selectedPolicies
      config.risk_policy_params = policyParams
    }
    // 快速风控参数注入
    if (quickStopLoss && selectedPolicies.includes('stop_loss')) {
      config.risk_policy_params = {
        ...(config.risk_policy_params as Record<string, unknown> ?? {}),
        stop_loss: { stop_loss_pct: Number(quickStopLoss) / 100 },
      }
    }
    if (quickDrawdownBreaker && selectedPolicies.includes('drawdown_breaker')) {
      config.risk_policy_params = {
        ...(config.risk_policy_params as Record<string, unknown> ?? {}),
        drawdown_breaker: { max_drawdown_pct: Number(quickDrawdownBreaker) / 100 },
      }
    }
    onChange(JSON.stringify(config, null, 2))
  }, [strategyType, factorsText, topN, rebalance, sizer, sizerParams, selectedPolicies, policyParams, maxPositionPct, maxLeverage, shortN, topSectors, topNPerSector, comboMethod, subStrategyConfigs, universeId, customAssets, quickStopLoss, quickDrawdownBreaker])

  const selectedSizerInfo = sizers?.find(s => s.name === sizer)

  return (
    <div className="space-y-4 p-4">
      {/* Strategy Type */}
      <div>
        <label className="text-xs text-gray-500 mb-1 block">策略类型</label>
        <select className="input w-full" value={strategyType} onChange={e => setStrategyType(e.target.value)}>
          <option value="StaticTopN">StaticTopN — 静态 Top N 截面动量</option>
          <option value="MLModelStrategy">MLModelStrategy — ML 模型预测</option>
          <option value="MultiFactor">MultiFactor — 多因子加权</option>
          <option value="MarketNeutral">MarketNeutral — 市场中性（多空）</option>
          <option value="SectorRotation">SectorRotation — 行业轮动</option>
          <option value="Combo">Combo — 组合策略</option>
        </select>
      </div>

      {/* Universe Selector */}
      <div>
        <label className="text-xs text-gray-500 mb-1 block">股票池</label>
        <select
          className="input w-full"
          value={universeId}
          onChange={e => {
            setUniverseId(e.target.value)
            if (e.target.value !== 'custom') setCustomAssets('')
          }}
        >
          {universes?.predefined.map(u => (
            <option key={u.id} value={u.id}>{u.name} — {u.description}</option>
          ))}
          <option value="custom">自定义股票代码</option>
        </select>
      </div>
      {universeId === 'custom' && (
        <div>
          <label className="text-xs text-gray-500 mb-1 block">自定义股票代码（逗号分隔）</label>
          <input
            className="input w-full"
            value={customAssets}
            onChange={e => setCustomAssets(e.target.value)}
            placeholder="SSE:600036,SZSE:000001,SZSE:300750"
          />
        </div>
      )}

      {/* Factors & Top N */}
      <div className="grid grid-cols-3 gap-3">
        <div className="col-span-2">
          <label className="text-xs text-gray-500 mb-1 block">因子列表（逗号分隔）</label>
          <input className="input w-full" value={factorsText} onChange={e => setFactorsText(e.target.value)}
            placeholder="ret_20d, vol_20d, momentum_20d" />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Top N</label>
          <input type="number" className="input w-full" value={topN} onChange={e => setTopN(e.target.value)} min={1} />
        </div>
      </div>

      {/* MarketNeutral: short_n */}
      {strategyType === 'MarketNeutral' && (
        <div className="border rounded-lg p-3 bg-blue-50">
          <div className="text-xs font-medium text-gray-600 mb-2">市场中性参数</div>
          <div>
            <label className="text-xs text-gray-500">做空数量 (Short N)</label>
            <input type="number" className="input w-full" value={shortN}
              onChange={e => setShortN(e.target.value)} min={1} />
          </div>
        </div>
      )}

      {/* SectorRotation params */}
      {strategyType === 'SectorRotation' && (
        <div className="border rounded-lg p-3 bg-blue-50">
          <div className="text-xs font-medium text-gray-600 mb-2">行业轮动参数</div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500">选行业数</label>
              <input type="number" className="input w-full" value={topSectors}
                onChange={e => setTopSectors(e.target.value)} min={1} />
            </div>
            <div>
              <label className="text-xs text-gray-500">每行业选股数</label>
              <input type="number" className="input w-full" value={topNPerSector}
                onChange={e => setTopNPerSector(e.target.value)} min={1} />
            </div>
          </div>
        </div>
      )}

      {/* Combo params */}
      {strategyType === 'Combo' && (
        <div className="border rounded-lg p-3 bg-blue-50">
          <div className="text-xs font-medium text-gray-600 mb-2">组合策略参数</div>
          <div className="mb-2">
            <label className="text-xs text-gray-500">合并方式</label>
            <select className="input w-full" value={comboMethod} onChange={e => setComboMethod(e.target.value)}>
              <option value="equal_weight">equal_weight — 等权合并</option>
              <option value="custom">custom — 自定义权重</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500">子策略配置 (JSON 数组)</label>
            <textarea className="input w-full font-mono text-xs" rows={4}
              value={subStrategyConfigs} onChange={e => setSubStrategyConfigs(e.target.value)}
              placeholder='[{"strategy_type":"StaticTopN","top_n":5,"sort_factor":"ret_20d"},{"strategy_type":"MultiFactor","top_n":5,"sort_factor":"vol_20d"}]' />
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">调仓频率</label>
          <select className="input w-full" value={rebalance} onChange={e => setRebalance(e.target.value)}>
            <option value="1d">每日</option>
            <option value="5d">每周</option>
            <option value="20d">每月</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">仓位管理器 (Sizer)</label>
          <select className="input w-full" value={sizer} onChange={e => { setSizer(e.target.value); setSizerParams({}) }}>
            {sizers?.map(s => (
              <option key={s.name} value={s.name}>{s.name} — {s.description}</option>
            )) ?? <option value="equal_weight">equal_weight</option>}
          </select>
        </div>
      </div>

      {/* Sizer params */}
      {selectedSizerInfo && selectedSizerInfo.params.length > 0 && (
        <div className="border rounded-lg p-3 bg-gray-50">
          <div className="text-xs font-medium text-gray-600 mb-2">Sizer 参数</div>
          <div className="grid grid-cols-2 gap-2">
            {selectedSizerInfo.params.map(p => (
              <div key={p.key}>
                <label className="text-xs text-gray-500">{p.description}</label>
                <input className="input w-full" placeholder={String(p.default)}
                  value={sizerParams[p.key] ?? ''}
                  onChange={e => setSizerParams(prev => ({ ...prev, [p.key]: e.target.value }))} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Risk limits */}
      <div className="border rounded-lg p-3">
        <div className="text-xs font-medium text-gray-600 mb-2">风控限制</div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500">单股最大仓位 %</label>
            <input type="number" className="input w-full" value={maxPositionPct}
              onChange={e => setMaxPositionPct(e.target.value)} min={0} max={1} step={0.01} />
          </div>
          <div>
            <label className="text-xs text-gray-500">最大杠杆</label>
            <input type="number" className="input w-full" value={maxLeverage}
              onChange={e => setMaxLeverage(e.target.value)} min={0} max={5} step={0.1} />
          </div>
        </div>
      </div>

      {/* 快速风控配置 — 最常用的3个参数直接展示 */}
      <div className="border rounded-lg p-3 bg-amber-50 space-y-3">
        <h4 className="text-sm font-medium text-amber-800">常用风控参数</h4>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">
              止损比例 (%)
              <span className="ml-1 text-gray-400 cursor-help" title="单笔持仓亏损超过此比例时强制平仓">ⓘ</span>
            </label>
            <input
              type="number"
              step={0.5}
              min={0}
              max={50}
              placeholder="不启用"
              value={quickStopLoss}
              onChange={e => {
                setQuickStopLoss(e.target.value)
                if (e.target.value && !selectedPolicies.includes('stop_loss')) {
                  setSelectedPolicies(prev => [...prev, 'stop_loss'])
                }
                if (!e.target.value) {
                  setSelectedPolicies(prev => prev.filter(p => p !== 'stop_loss'))
                }
              }}
              className="input w-full text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">
              单仓最大比例 (%)
              <span className="ml-1 text-gray-400 cursor-help" title="单只股票持仓不超过组合的此比例">ⓘ</span>
            </label>
            <input
              type="number"
              step={1}
              min={1}
              max={100}
              value={maxPositionPct ? String(Number(maxPositionPct) * 100) : ''}
              onChange={e => {
                const pct = e.target.value ? String(Number(e.target.value) / 100) : ''
                setMaxPositionPct(pct)
              }}
              className="input w-full text-sm"
              placeholder="不限制"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">
              最大回撤熔断 (%)
              <span className="ml-1 text-gray-400 cursor-help" title="组合从高点回撤超过此比例时暂停交易">ⓘ</span>
            </label>
            <input
              type="number"
              step={1}
              min={0}
              max={50}
              placeholder="不启用"
              value={quickDrawdownBreaker}
              onChange={e => {
                setQuickDrawdownBreaker(e.target.value)
                if (e.target.value && !selectedPolicies.includes('drawdown_breaker')) {
                  setSelectedPolicies(prev => [...prev, 'drawdown_breaker'])
                }
                if (!e.target.value) {
                  setSelectedPolicies(prev => prev.filter(p => p !== 'drawdown_breaker'))
                }
              }}
              className="input w-full text-sm"
            />
          </div>
        </div>
      </div>

      {/* Risk policies */}
      <div className="border rounded-lg p-3">
        <div className="text-xs font-medium text-gray-600 mb-2">风控策略</div>
        <div className="grid grid-cols-2 gap-2">
          {policies?.map(p => (
            <label key={p.name} className="flex items-start gap-2 text-sm cursor-pointer">
              <input type="checkbox" className="mt-1"
                checked={selectedPolicies.includes(p.name)}
                onChange={e => {
                  setSelectedPolicies(prev =>
                    e.target.checked ? [...prev, p.name] : prev.filter(n => n !== p.name)
                  )
                }} />
              <div>
                <div className="font-medium text-gray-700">{p.name}</div>
                <div className="text-xs text-gray-400">{p.description}</div>
              </div>
            </label>
          ))}
        </div>

        {/* Policy params for selected policies */}
        {selectedPolicies.length > 0 && (
          <div className="mt-3 pt-3 border-t space-y-2">
            {selectedPolicies.map(pName => {
              const pInfo = policies?.find(p => p.name === pName)
              if (!pInfo || pInfo.params.length === 0) return null
              // Skip detailed params for policies controlled by quick controls
              if (pName === 'stop_loss' && quickStopLoss) return null
              if (pName === 'drawdown_breaker' && quickDrawdownBreaker) return null
              return (
                <div key={pName} className="bg-gray-50 rounded p-2">
                  <div className="text-xs font-medium text-gray-500 mb-1">{pName}</div>
                  <div className="grid grid-cols-2 gap-2">
                    {pInfo.params.map(p => (
                      <div key={p.key}>
                        <label className="text-xs text-gray-400">{p.description}</label>
                        <input className="input w-full" placeholder={String(p.default)}
                          value={policyParams[pName]?.[p.key] ?? ''}
                          onChange={e => setPolicyParams(prev => ({
                            ...prev,
                            [pName]: { ...(prev[pName] ?? {}), [p.key]: e.target.value },
                          }))} />
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

function WalkForwardPreview({
  startDate, endDate, nSplits, gapDays, trainRatio,
}: {
  startDate: string; endDate: string; nSplits: number; gapDays: number; trainRatio: number
}) {
  const folds = useMemo(() => {
    if (!startDate || !endDate || nSplits < 2) return []
    const start = new Date(startDate)
    const end = new Date(endDate)
    const totalDays = (end.getTime() - start.getTime()) / 86400000
    if (totalDays < 30) return []

    const testDays = Math.floor(totalDays * (1 - trainRatio) / nSplits)
    const result: Array<{ trainStart: Date; trainEnd: Date; testStart: Date; testEnd: Date }> = []

    for (let i = 0; i < nSplits; i++) {
      const trainEnd = new Date(start.getTime() + (trainRatio + (1 - trainRatio) * i / nSplits) * totalDays * 86400000)
      const testStart = new Date(trainEnd.getTime() + gapDays * 86400000)
      const testEnd = new Date(testStart.getTime() + testDays * 86400000)
      if (testEnd > end) break
      result.push({ trainStart: start, trainEnd, testStart, testEnd })
    }
    return result
  }, [startDate, endDate, nSplits, gapDays, trainRatio])

  if (folds.length === 0) return null

  const totalMs = new Date(endDate).getTime() - new Date(startDate).getTime()
  const pct = (d: Date) => ((d.getTime() - new Date(startDate).getTime()) / totalMs * 100)

  return (
    <div className="mt-2">
      <label className="block text-xs text-gray-500 mb-1">分割预览</label>
      <div className="relative h-16 bg-gray-100 rounded">
        {folds.map((f, i) => (
          <div key={i} className="absolute top-0 h-full">
            <div className="absolute bg-blue-400 opacity-30 h-full rounded-l"
              style={{ left: `${pct(f.trainStart)}%`, width: `${pct(f.trainEnd) - pct(f.trainStart)}%` }} />
            <div className="absolute bg-green-400 opacity-60 h-full rounded-r"
              style={{ left: `${pct(f.testStart)}%`, width: `${pct(f.testEnd) - pct(f.testStart)}%` }} />
          </div>
        ))}
        <div className="absolute bottom-0 left-0 right-0 flex justify-between text-xs text-gray-400 px-1">
          <span>{startDate}</span>
          <span>{endDate}</span>
        </div>
      </div>
      <div className="flex gap-4 mt-1 text-xs text-gray-500">
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-400 opacity-30 rounded" />Train</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 bg-green-400 opacity-60 rounded" />OOS</span>
      </div>
    </div>
  )
}

function BacktestRunModal({
  strategyId,
  configText,
  onClose,
}: {
  strategyId: string
  configText: string
  onClose: () => void
}) {
  const navigate = useNavigate()
  const parsed = useMemo(() => {
    try { return JSON.parse(configText) } catch { return {} }
  }, [configText])
  const factors: string[] = parsed.factors ?? ['ret_20d']
  const defaultTopN = parsed.top_n ?? 10

  const [startDate, setStartDate] = useState('2025-01-01')
  const [endDate, setEndDate] = useState('2025-06-30')
  const [topN, setTopN] = useState(String(defaultTopN))
  const [sortFactor, setSortFactor] = useState(factors[0])
  const [datasetVersion, setDatasetVersion] = useState('')
  const [universeId, setUniverseId] = useState(parsed.universe_id ?? 'all')
  const [customAssets, setCustomAssets] = useState('')
  const [benchmarkId, setBenchmarkId] = useState('')
  const [scoringRunId, setScoringRunId] = useState('')
  const [scoringWarning, setScoringWarning] = useState('')
  const [mlModelVersion, setMlModelVersion] = useState(
    (parsed as Record<string, unknown>).model_version as string
    ?? (parsed as Record<string, unknown>).model_id as string
    ?? ''
  )
  const [mlLabelName, setMlLabelName] = useState(
    (parsed as Record<string, unknown>).label_name as string ?? 'ret_5d'
  )

  // Data split mode
  const [splitMode, setSplitMode] = useState<'none' | 'oos' | 'walkforward'>('none')
  const [trainEndDate, setTrainEndDate] = useState('2024-01-01')
  const [evalMode, setEvalMode] = useState<'test' | 'valid' | 'all'>('test')

  // Walk-forward config
  const [wfSplits, setWfSplits] = useState(3)
  const [wfGapDays, setWfGapDays] = useState(5)
  const [wfWindowType, setWfWindowType] = useState<'expanding' | 'sliding'>('expanding')
  const [wfTrainRatio, setWfTrainRatio] = useState(70)
  const [wfValidRatio, setWfValidRatio] = useState(15)

  const { data: datasets } = useQuery({
    queryKey: queryKeys.datasets.list(10),
    queryFn: () => datasetsApi.list(10),
  })

  const { data: universes } = useQuery({
    queryKey: ['datasets', 'universes'],
    queryFn: datasetsApi.universes,
    staleTime: 300_000,
  })

  const { data: mlExperiments } = useQuery({
    queryKey: ['ml', 'experiments', 'completed'],
    queryFn: () => mlApi.experiments(100),
    enabled: parsed.strategy_type === 'MLModelStrategy',
    staleTime: 30_000,
    select: (data) => data.items?.filter(
      (e: { status: string }) => e.status === 'completed' || e.status === 'done'
    ) ?? [],
  })

  // Load pending scoring run from sessionStorage
  useEffect(() => {
    const pending = sessionStorage.getItem('pendingScoring')
    if (pending) {
      try {
        const { runId, start, end } = JSON.parse(pending)
        setScoringRunId(runId ?? '')
        if (start) setStartDate(start)
        if (end) setEndDate(end)
      } catch { /* ignore */ }
      sessionStorage.removeItem('pendingScoring')
    }
  }, [])

  // Auto-select current dataset
  useEffect(() => {
    if (datasets?.items.length && !datasetVersion) {
      const current = datasets.items.find(d => d.is_current) ?? datasets.items[0]
      setDatasetVersion(current.version_id)
    }
  }, [datasets, datasetVersion])

  const queryClient = useQueryClient()
  const [jobId, setJobId] = useState<string | null>(null)

  const { data: jobStatus } = useQuery({
    queryKey: ['backtest-job', jobId],
    queryFn: () => backtestsApi.pollJob(jobId!),
    enabled: !!jobId,
    refetchInterval: (query: any) =>
      query.state.data?.status === 'running' ? 2000 : false,
  })

  const runMutation = useMutation({
    mutationFn: backtestsApi.create,
    onSuccess: (data) => {
      if (data.warning) {
        setScoringWarning(data.warning as string)
      }
      if (data.job_id) {
        setJobId(data.job_id)
      } else {
        queryClient.refetchQueries({ queryKey: queryKeys.backtests.all }).then(() => {
          onClose()
          navigate('/backtests')
        })
      }
    },
    onError: (error: Error) => {
      toast.error(`回测提交失败: ${error.message}`)
    },
  })

  // Job completion handler
  useEffect(() => {
    if (jobStatus?.status === 'completed') {
      queryClient.refetchQueries({ queryKey: queryKeys.backtests.all }).then(() => {
        onClose()
        navigate(`/backtests?run_id=${jobStatus.run_id}`)
      })
    } else if (jobStatus?.status === 'failed') {
      toast.error(`回测失败: ${jobStatus.error ?? '未知错误'}`)
      queryClient.invalidateQueries({ queryKey: queryKeys.backtests.all })
    }
  }, [jobStatus, queryClient, onClose, navigate])

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-[500px] max-w-[95vw]">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="font-semibold text-gray-900">执行回测</h2>
          <button className="text-gray-400 hover:text-gray-600" onClick={onClose}>✕</button>
        </div>
        <div className="p-4 space-y-4">
          <div>
            <label className="block text-sm text-gray-600 mb-1">策略</label>
            <div className="px-3 py-2 bg-gray-50 border rounded-lg text-sm">{strategyId}</div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">开始日期</label>
              <input type="date" className="input w-full" value={startDate} onChange={e => setStartDate(e.target.value)} />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">结束日期</label>
              <input type="date" className="input w-full" value={endDate} onChange={e => setEndDate(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Top N</label>
              <input type="number" className="input w-full" value={topN} onChange={e => setTopN(e.target.value)} min={1} />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">排序因子</label>
              <select className="input w-full" value={sortFactor} onChange={e => setSortFactor(e.target.value)}>
                {factors.map(f => <option key={f} value={f}>{f}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">数据集</label>
            <select className="input w-full" value={datasetVersion} onChange={e => setDatasetVersion(e.target.value)}>
              {datasets?.items.map(d => (
                <option key={d.version_id} value={d.version_id}>
                  {d.dataset_name} ({d.start_date} ~ {d.end_date}) — {d.asset_count ?? '?'} 股
                  {d.is_current ? ' ✓' : ''}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">股票池</label>
            <select
              className="input w-full"
              value={universeId}
              onChange={e => {
                setUniverseId(e.target.value)
                if (e.target.value !== 'custom') setCustomAssets('')
              }}
            >
              {universes?.predefined.map(u => (
                <option key={u.id} value={u.id}>{u.name} — {u.description}</option>
              ))}
              <option value="custom">自定义股票代码</option>
            </select>
          </div>
          {universeId === 'custom' && (
            <div>
              <label className="block text-sm text-gray-600 mb-1">自定义股票代码（逗号分隔）</label>
              <input
                type="text"
                className="input w-full"
                value={customAssets}
                onChange={e => setCustomAssets(e.target.value)}
                placeholder="SSE:600036,SZSE:000001,SZSE:300750"
              />
            </div>
          )}
          <div>
            <label className="block text-sm text-gray-600 mb-1">基准对比（可选）</label>
            <select value={benchmarkId} onChange={e => setBenchmarkId(e.target.value)} className="input w-full">
              <option value="">— 不设基准 —</option>
              <option value="SSE:000300">沪深300</option>
              <option value="SSE:000905">中证500</option>
              <option value="SSE:000852">中证1000</option>
              <option value="SSE:000001">上证指数</option>
              <option value="SZSE:399001">深证成指</option>
            </select>
          </div>

          {/* ML 模型选择（仅 MLModelStrategy 显示）*/}
          {parsed.strategy_type === 'MLModelStrategy' && (
            <div className="border rounded-lg p-3 bg-blue-50 space-y-3">
              <h4 className="text-sm font-medium text-blue-800">ML 模型配置</h4>
              <div>
                <label className="block text-xs text-gray-600 mb-1">选择已训练模型</label>
                <select
                  value={mlModelVersion}
                  onChange={e => {
                    setMlModelVersion(e.target.value)
                    const exp = mlExperiments?.find(
                      (ex: { run_id: string; model_id?: string }) =>
                        ex.run_id === e.target.value || ex.model_id === e.target.value
                    )
                    if (exp?.target_name) setMlLabelName(exp.target_name)
                  }}
                  className="input w-full text-sm"
                >
                  <option value="">— 选择已完成的实验 —</option>
                  {mlExperiments?.map((exp: {
                    run_id: string
                    model_id?: string
                    trainer_name?: string
                    target_name?: string
                    metrics?: { sharpe?: number }
                    started_at?: string | number
                  }) => (
                    <option key={exp.run_id} value={exp.model_id ?? exp.run_id}>
                      {exp.run_id.slice(0, 10)}… · {exp.trainer_name ?? '—'} · target={exp.target_name ?? '—'}
                      {exp.metrics?.sharpe != null ? ` · Sharpe=${exp.metrics.sharpe.toFixed(2)}` : ''}
                    </option>
                  ))}
                </select>
                {mlExperiments !== undefined && mlExperiments.length === 0 && (
                  <p className="text-xs text-gray-400 mt-1">
                    暂无已完成实验，请先在"机器学习"页面训练模型
                  </p>
                )}
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">预测标签</label>
                <select
                  value={mlLabelName}
                  onChange={e => setMlLabelName(e.target.value)}
                  className="input w-full text-sm"
                >
                  <option value="ret_1d">ret_1d（1日收益）</option>
                  <option value="ret_5d">ret_5d（5日收益）</option>
                  <option value="ret_10d">ret_10d（10日收益）</option>
                  <option value="ret_20d">ret_20d（20日收益）</option>
                </select>
              </div>
            </div>
          )}

          {scoringRunId && (
            <div className="p-2 bg-purple-50 border border-purple-200 rounded text-xs text-purple-700">
              📊 使用截面打分结果：<span className="font-mono">{scoringRunId.slice(0, 12)}…</span>
              <br />日期范围已限定为打分数据覆盖区间
            </div>
          )}

          {/* Data Split Section */}
          <div className="border-t pt-4">
            <label className="block text-sm text-gray-600 mb-2">数据分割</label>
            <select
              className="input w-full"
              value={splitMode}
              onChange={e => setSplitMode(e.target.value as typeof splitMode)}
            >
              <option value="none">不分割（用全部数据回测）</option>
              <option value="oos">OOS 分割（训练/测试分离）</option>
              <option value="walkforward">Walk-Forward（滚动评估）</option>
            </select>
          </div>

          {/* OOS Split Config */}
          {splitMode === 'oos' && (
            <div className="grid grid-cols-2 gap-4 pl-4 border-l-2 border-blue-200">
              <div>
                <label className="block text-sm text-gray-600 mb-1">Train 截止日</label>
                <input type="date" className="input w-full" value={trainEndDate}
                  onChange={e => setTrainEndDate(e.target.value)} />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">评估模式</label>
                <select className="input w-full" value={evalMode}
                  onChange={e => setEvalMode(e.target.value as typeof evalMode)}>
                  <option value="test">Test（仅在测试集回测）</option>
                  <option value="valid">Valid（仅在验证集回测）</option>
                  <option value="all">All（用全部数据回测）</option>
                </select>
              </div>
            </div>
          )}

          {/* Walk-Forward Config */}
          {splitMode === 'walkforward' && (
            <div className="pl-4 border-l-2 border-green-200 space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">分割数</label>
                  <input type="number" className="input w-full" value={wfSplits}
                    onChange={e => setWfSplits(Number(e.target.value))} min={2} max={10} />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">间隔天数</label>
                  <input type="number" className="input w-full" value={wfGapDays}
                    onChange={e => setWfGapDays(Number(e.target.value))} min={0} />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">窗口类型</label>
                  <select className="input w-full" value={wfWindowType}
                    onChange={e => setWfWindowType(e.target.value as typeof wfWindowType)}>
                    <option value="expanding">Expanding（扩展窗口）</option>
                    <option value="sliding">Sliding（滑动窗口）</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">Train %</label>
                  <input type="number" className="input w-full" value={wfTrainRatio}
                    onChange={e => setWfTrainRatio(Number(e.target.value))} min={10} max={90} />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">Valid %</label>
                  <input type="number" className="input w-full" value={wfValidRatio}
                    onChange={e => setWfValidRatio(Number(e.target.value))} min={5} max={30} />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">Test %</label>
                  <input type="number" className="input w-full" disabled
                    value={100 - wfTrainRatio - wfValidRatio} />
                </div>
              </div>
              {/* Timeline preview */}
              <WalkForwardPreview
                startDate={startDate} endDate={endDate}
                nSplits={wfSplits} gapDays={wfGapDays}
                trainRatio={wfTrainRatio / 100}
              />
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 p-4 border-t flex-wrap">
          {scoringWarning && (
            <div className="w-full text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
              ⚠ {scoringWarning}
            </div>
          )}
          {jobId && jobStatus?.status === 'running' && (
            <div className="flex items-center gap-2 text-sm text-blue-600">
              <div className="animate-spin w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full" />
              回测运行中…
            </div>
          )}
          {jobId && jobStatus?.status === 'failed' && (
            <div className="text-sm text-red-600">
              失败：{jobStatus.error ?? '未知错误'}
            </div>
          )}
          <button className="btn-secondary" onClick={onClose}>
            {jobId ? '关闭' : '取消'}
          </button>
          {!jobId && (
          <button
            className="btn-primary"
            disabled={runMutation.isPending || !datasetVersion}
            onClick={() => {
              const body: Record<string, unknown> = {
                strategy_id: strategyId,
                dataset_version: datasetVersion,
                start_date: startDate,
                end_date: endDate,
                top_n: Number(topN) || 10,
                sort_factor: sortFactor,
                strategy_type: parsed.strategy_type ?? 'StaticTopN',
                universe_id: universeId === 'custom' ? 'all' : universeId,
                benchmark_asset_id: benchmarkId || "",
                ...(scoringRunId ? { scoring_run_id: scoringRunId } : {}),
              }
              if (parsed.strategy_type === 'MarketNeutral') {
                body.short_n = parsed.short_n ?? 10
              }
              if (parsed.strategy_type === 'SectorRotation') {
                body.sector_map = parsed.sector_map ?? {}
                body.top_sectors = parsed.top_sectors ?? 3
                body.top_n_per_sector = parsed.top_n_per_sector ?? 3
              }
              if (parsed.strategy_type === 'Combo') {
                body.sub_strategy_configs = parsed.sub_strategy_configs ?? []
                body.combo_method = parsed.combo_method ?? 'equal_weight'
              }
              if (parsed.strategy_type === 'MLModelStrategy') {
                body.model_version = mlModelVersion
                  || (parsed as Record<string, unknown>).model_version
                  || (parsed as Record<string, unknown>).model_id
                  || ''
                body.label_name = mlLabelName
                  || (parsed as Record<string, unknown>).label_name
                  || 'ret_5d'
              }
              if (parsed.strategy_type === 'CustomWeightStrategy') {
                body.custom_weights = (parsed as Record<string, unknown>).custom_weights ?? {}
              }
              // Data split params
              if (splitMode === 'oos') {
                body.train_end_date = trainEndDate
                body.eval_mode = evalMode
              }
              if (splitMode === 'walkforward') {
                body.walk_forward = {
                  n_splits: wfSplits,
                  gap_days: wfGapDays,
                  window_type: wfWindowType,
                  purge_window: 0,
                }
              }
              runMutation.mutate(body as any)
            }}
          >
            {runMutation.isPending ? '执行中…' : '执行回测'}
          </button>
          )}
        </div>
      </div>
    </div>
  )
}

export function StrategiesPage() {
  const qc = useQueryClient()
  const location = useLocation()
  const [editingId, setEditingId] = useState<string | 'new' | null>(null)
  const [showVersions, setShowVersions] = useState(false)
  const [configText, setConfigText] = useState(DEFAULT_CONFIG)
  const [newId, setNewId] = useState('')
  const [backtestStrategyId, setBacktestStrategyId] = useState<string | null>(null)
  const [backtestConfigText, setBacktestConfigText] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [configError, setConfigError] = useState<string | null>(null)
  const [strategyIdError, setStrategyIdError] = useState<string | null>(null)
  const [editorMode, setEditorMode] = useState<'json' | 'builder'>('json')

  const { data, isLoading } = useQuery({
    queryKey: extendedQueryKeys.strategies.list(),
    queryFn: strategiesApi.list,
  })

  const { data: versions, refetch: refetchVersions } = useQuery({
    queryKey: ['strategies', editingId, 'versions'],
    queryFn: () => strategiesApi.versions(editingId!),
    enabled: !!editingId && editingId !== 'new' && showVersions,
    staleTime: 5_000,
  })

  useEffect(() => {
    const state = location.state as {
      prefill?: { strategy_id?: string; config?: string }
      openBacktest?: boolean
      scoringRunId?: string
      scoringDateRange?: { start?: string; end?: string }
    } | null
    if (!state) return
    const { prefill, openBacktest, scoringRunId, scoringDateRange } = state
    if (prefill) {
      if (prefill.strategy_id) setNewId(prefill.strategy_id)
      if (prefill.config) setConfigText(prefill.config)
      setEditingId('new')
    }
    if (openBacktest && prefill?.strategy_id && !prefill.config) {
      // If strategy already exists, open backtest modal directly
      setBacktestStrategyId(prefill.strategy_id)
      setBacktestConfigText(prefill.config ?? '')
    }
    if (scoringRunId) {
      sessionStorage.setItem('pendingScoring', JSON.stringify({
        runId: scoringRunId,
        start: scoringDateRange?.start,
        end: scoringDateRange?.end,
      }))
    }
  }, [location.state])

  function validateConfig(text: string): string | null {
    if (!text.trim()) return null
    try {
      JSON.parse(text)
      return null
    } catch (e) {
      return `JSON 格式错误：${(e as Error).message}`
    }
  }

  const createMutation = useMutation({
    mutationFn: () => strategiesApi.create({ strategy_id: newId, config_text: configText }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: extendedQueryKeys.strategies.list() })
      setEditingId(null)
    },
    onError: (err: Error) => {
      const msg = err.message
      if (msg.includes('409') || msg.toLowerCase().includes('already exists') || msg.includes('已存在')) {
        setStrategyIdError('策略 ID 已存在，请使用其他名称')
      } else {
        toast.error(`保存失败：${msg}`)
      }
    },
  })

  const updateMutation = useMutation({
    mutationFn: (id: string) => strategiesApi.update(id, { config_text: configText }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: extendedQueryKeys.strategies.list() })
      qc.invalidateQueries({ queryKey: ['strategies', editingId, 'versions'] })
      setEditingId(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => strategiesApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: extendedQueryKeys.strategies.list() })
      toast.success('策略已删除')
      setDeleteTarget(null)
    },
    onError: (err: Error) => {
      toast.error(`删除失败：${err.message}`)
      setDeleteTarget(null)
    },
  })

  function openEdit(item: { strategy_id: string; config_text: string }) {
    setEditingId(item.strategy_id)
    setConfigText(item.config_text)
    setShowVersions(false)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">策略配置</h1>
          <p className="page-subtitle">创建和管理量化策略配置（JSON）</p>
        </div>
        <button className="btn-primary" onClick={() => { setEditingId('new'); setConfigText(DEFAULT_CONFIG); setNewId(''); setShowVersions(false) }}>
          + 新建策略
        </button>
      </div>

      {isLoading && <p className="text-gray-400">Loading…</p>}

      {/* Editor modal */}
      {editingId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-[700px] max-w-[95vw] max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="font-semibold text-gray-900">
                {editingId === 'new' ? '新建策略' : `编辑策略: ${editingId}`}
              </h2>
              <button className="text-gray-400 hover:text-gray-600" onClick={() => setEditingId(null)}>✕</button>
            </div>
            {editingId === 'new' && (
              <div className="p-4 border-b">
                <input
                  className="input"
                  placeholder="策略 ID（唯一标识符）"
                  value={newId}
                  onChange={e => {
                    setNewId(e.target.value)
                    setStrategyIdError(null)
                  }}
                />
                {strategyIdError && (
                  <p className="mt-1 text-xs text-red-600">{strategyIdError}</p>
                )}
              </div>
            )}
            {/* Mode toggle */}
            <div className="flex gap-1 px-4 pt-3">
              <button
                className={`px-3 py-1.5 text-sm rounded-t-lg border-b-2 ${
                  editorMode === 'builder' ? 'border-blue-600 text-blue-700 bg-blue-50' : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
                onClick={() => setEditorMode('builder')}
              >
                可视化构建
              </button>
              <button
                className={`px-3 py-1.5 text-sm rounded-t-lg border-b-2 ${
                  editorMode === 'json' ? 'border-blue-600 text-blue-700 bg-blue-50' : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
                onClick={() => setEditorMode('json')}
              >
                JSON 编辑
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              {editorMode === 'builder' ? (
                <StrategyBuilder
                  initialConfig={configText}
                  onChange={v => {
                    setConfigText(v)
                    setConfigError(null)
                  }}
                />
              ) : (
                <>
                  <Editor
                    height="400px"
                    language="json"
                    value={configText}
                    onChange={v => {
                      const value = v ?? ''
                      setConfigText(value)
                      setConfigError(validateConfig(value))
                    }}
                    options={{ minimap: { enabled: false }, fontSize: 13, scrollBeyondLastLine: false }}
                  />
                  {configError && (
                    <p className="mt-1 px-4 text-xs text-red-600">{configError}</p>
                  )}
                </>
              )}
            </div>
            {/* 版本历史（仅编辑已有策略时显示）*/}
            {editingId && editingId !== 'new' && (
              <div className="mx-4 mb-3 border-t pt-3">
                <button
                  type="button"
                  onClick={() => setShowVersions(v => !v)}
                  className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1"
                >
                  <span>{showVersions ? '▾' : '▸'}</span>
                  版本历史（最近 5 次）
                </button>
                {showVersions && (
                  <div className="mt-2 space-y-1">
                    {!versions ? (
                      <p className="text-xs text-gray-400">加载中…</p>
                    ) : versions.items.length === 0 ? (
                      <p className="text-xs text-gray-400">暂无历史版本</p>
                    ) : (
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-left text-gray-400 border-b">
                            <th className="py-1">时间</th>
                            <th className="py-1">摘要</th>
                            <th className="py-1 w-16">操作</th>
                          </tr>
                        </thead>
                        <tbody>
                          {versions.items.map((v, idx) => (
                            <tr key={v.version_id} className={`border-b ${idx === 0 ? 'opacity-50' : ''}`}>
                              <td className="py-1 text-gray-500 font-mono">
                                {new Date(v.created_at).toLocaleString('zh-CN', {
                                  month: '2-digit', day: '2-digit',
                                  hour: '2-digit', minute: '2-digit',
                                })}
                              </td>
                              <td className="py-1 text-gray-700 max-w-[200px] truncate" title={v.summary}>
                                {idx === 0 ? `${v.summary}（当前）` : v.summary}
                              </td>
                              <td className="py-1">
                                {idx !== 0 && (
                                  <button
                                    className="text-brand-600 hover:underline"
                                    onClick={async () => {
                                      if (!confirm(`回滚到此版本？\n${v.summary}`)) return
                                      try {
                                        await strategiesApi.rollback(editingId!, v.version_id)
                                        const fresh = await strategiesApi.get(editingId!)
                                        setConfigText(fresh.config_text)
                                        refetchVersions()
                                        toast.success('已回滚到历史版本')
                                      } catch (err) {
                                        toast.error(`回滚失败：${(err as Error).message}`)
                                      }
                                    }}
                                  >
                                    恢复
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
              </div>
            )}
            <div className="flex justify-end gap-2 p-4 border-t">
              <button className="btn-secondary" onClick={() => setEditingId(null)}>取消</button>
              <button
                className="btn-primary"
                disabled={
                  (editingId === 'new' && !newId.trim()) ||
                  configError !== null ||
                  createMutation.isPending ||
                  updateMutation.isPending
                }
                onClick={() => {
                  if (editingId === 'new') createMutation.mutate()
                  else updateMutation.mutate(editingId)
                }}
              >
                {(createMutation.isPending || updateMutation.isPending) ? '保存中…' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {!data?.items.length && !isLoading && (
          <div className="col-span-2 text-center text-gray-400 py-12">暂无策略，点击"新建策略"开始</div>
        )}
        {data?.items.map(s => (
          <div key={s.strategy_id} className="card">
            <div className="flex items-start justify-between">
              <div>
                <div className="font-semibold text-gray-900">{s.strategy_id}</div>
                <div className="text-xs text-gray-400 mt-1">更新于 {s.updated_at?.slice(0, 16) ?? '—'}</div>
              </div>
              <div className="flex gap-2">
                <button
                  className="btn-secondary text-xs px-3 py-1 text-green-600 border-green-300 hover:bg-green-50"
                  onClick={() => { setBacktestStrategyId(s.strategy_id); setBacktestConfigText(s.config_text) }}
                >▶ 回测</button>
                <button className="btn-secondary text-xs px-3 py-1" onClick={() => openEdit(s)}>编辑</button>
                <button
                  className="btn-danger text-xs px-3 py-1"
                  onClick={() => setDeleteTarget(s.strategy_id)}
                >删除</button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {backtestStrategyId && (
        <BacktestRunModal
          strategyId={backtestStrategyId}
          configText={backtestConfigText}
          onClose={() => setBacktestStrategyId(null)}
        />
      )}

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title="确认删除策略"
        message={`确定删除策略 "${deleteTarget}"？此操作不可撤销。`}
        confirmLabel="删除"
        variant="danger"
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget)
        }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}

import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { datasetsApi, riskApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { ConditionEditor } from '@/components/strategies/ConditionEditor'
import { RuleConditionEditor } from '@/components/strategies/RuleConditionEditor'
import { StrategyTemplates, type StrategyTemplate } from '@/components/strategies/StrategyTemplates'

interface StrategyBuilderProps {
  initialConfig: string
  onChange: (json: string) => void
}

export function StrategyBuilder({ initialConfig, onChange }: StrategyBuilderProps) {
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
  const [shortN, setShortN] = useState(String(parsed.short_n ?? 10))
  const [topSectors, setTopSectors] = useState(String(parsed.top_sectors ?? 3))
  const [topNPerSector, setTopNPerSector] = useState(String(parsed.top_n_per_sector ?? 3))
  const [comboMethod, setComboMethod] = useState(parsed.combo_method ?? 'equal_weight')
  const [subStrategyConfigs, setSubStrategyConfigs] = useState<string>(
    JSON.stringify(parsed.sub_strategy_configs ?? [], null, 2)
  )
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
  const [market, setMarket] = useState(parsed.market_rule?.market ?? 'CN')
  const [adjType, setAdjType] = useState(parsed.market_rule?.adj_type ?? 'forward')
  // IndicatorSignal state
  const [entryConditions, setEntryConditions] = useState<string[]>(
    parsed.entry_conditions ?? ['']
  )
  const [exitConditions, setExitConditions] = useState<string[]>(
    parsed.exit_conditions ?? ['']
  )
  const [maxPositions, setMaxPositions] = useState(String(parsed.max_positions ?? 10))
  const [filterST, setFilterST] = useState(parsed.filters?.exclude_st ?? true)
  const [filterSuspended, setFilterSuspended] = useState(parsed.filters?.exclude_suspended ?? true)
  const [filterLimitUpDown, setFilterLimitUpDown] = useState(parsed.filters?.exclude_limit_up_down ?? true)
  const [editorMode, setEditorMode] = useState<'ui' | 'code'>('ui')
  const [showTemplates, setShowTemplates] = useState(false)

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
    if (strategyType === 'IndicatorSignal') {
      config.entry_conditions = entryConditions.filter(c => c.trim())
      config.exit_conditions = exitConditions.filter(c => c.trim())
      config.max_positions = Number(maxPositions) || 10
      config.filters = {
        exclude_st: filterST,
        exclude_suspended: filterSuspended,
        exclude_limit_up_down: filterLimitUpDown,
      }
      // Extract indicator specs from DSL conditions
      const allDsl = [...entryConditions, ...exitConditions].filter(c => c.trim()).join(' ')
      const indicatorSpecs: { name: string; params: Record<string, number> }[] = []
      const specMap = new Map<string, Record<string, number>>()
      const indicatorPattern = /(\w+)\(([^)]*)\)/g
      let m: RegExpExecArray | null
      while ((m = indicatorPattern.exec(allDsl)) !== null) {
        const name = m[1]
        const paramStr = m[2]
        if (!specMap.has(name) && paramStr) {
          const nums = paramStr.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n))
          if (nums.length > 0) {
            const keys = ['period', 'fast', 'slow', 'signal', 'std_dev', 'k_period', 'd_period']
            const params: Record<string, number> = {}
            nums.forEach((n, i) => { if (keys[i]) params[keys[i]] = n })
            specMap.set(name, params)
          }
        }
      }
      specMap.forEach((params, name) => indicatorSpecs.push({ name, params }))
      if (indicatorSpecs.length > 0) {
        config.indicator_specs = indicatorSpecs
      }
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
    config.market_rule = { market, adj_type: adjType }
    onChange(JSON.stringify(config, null, 2))
  }, [strategyType, factorsText, topN, rebalance, sizer, sizerParams, selectedPolicies, policyParams, maxPositionPct, maxLeverage, shortN, topSectors, topNPerSector, comboMethod, subStrategyConfigs, universeId, customAssets, quickStopLoss, quickDrawdownBreaker, market, adjType, entryConditions, exitConditions, maxPositions, filterST, filterSuspended, filterLimitUpDown])

  // Handle template selection — populate entry/exit conditions
  const handleTemplateSelect = (tpl: StrategyTemplate) => {
    setEntryConditions(tpl.entry.length > 0 ? tpl.entry : [''])
    setExitConditions(tpl.exit.length > 0 ? tpl.exit : [''])
    setShowTemplates(false)
  }

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
          <option value="IndicatorSignal">IndicatorSignal — 指标信号</option>
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

      {/* IndicatorSignal params */}
      {strategyType === 'IndicatorSignal' && (
        <div className="border rounded-lg p-3 bg-blue-50 space-y-4">
          <div className="text-xs font-medium text-gray-600 mb-2">指标信号参数</div>

          {/* Mode toggle + template button */}
          <div className="flex gap-2 mb-4">
            <button
              className={`text-xs px-3 py-1.5 rounded transition-colors ${editorMode === 'ui' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}`}
              onClick={() => setEditorMode('ui')}
            >
              UI 模式
            </button>
            <button
              className={`text-xs px-3 py-1.5 rounded transition-colors ${editorMode === 'code' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}`}
              onClick={() => setEditorMode('code')}
            >
              代码模式
            </button>
            <button
              className="text-xs px-3 py-1.5 rounded bg-white text-gray-600 border border-gray-300 hover:bg-gray-50 transition-colors"
              onClick={() => setShowTemplates(true)}
            >
              加载模板
            </button>
          </div>

          {/* Template modal */}
          {showTemplates && (
            <div className="border rounded-lg p-3 bg-white">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-gray-600">选择策略模板</span>
                <button
                  className="text-xs text-gray-400 hover:text-gray-600"
                  onClick={() => setShowTemplates(false)}
                >
                  关闭
                </button>
              </div>
              <StrategyTemplates onSelect={handleTemplateSelect} />
            </div>
          )}

          {/* Entry conditions */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-gray-500 font-medium">入场条件</label>
              <button
                className="text-xs text-blue-600 hover:text-blue-800"
                onClick={() => setEntryConditions(prev => [...prev, ''])}
              >
                + 添加条件
              </button>
            </div>
            {entryConditions.map((cond, idx) => (
              <div key={idx} className="mb-2">
                {editorMode === 'ui' ? (
                  <ConditionEditor
                    label={`入场条件 ${idx + 1}`}
                    value={cond}
                    onChange={(dsl) => {
                      setEntryConditions(prev => prev.map((c, i) => i === idx ? dsl : c))
                    }}
                  />
                ) : (
                  <RuleConditionEditor
                    label={`入场条件 ${idx + 1}`}
                    value={cond}
                    onChange={(dsl) => {
                      setEntryConditions(prev => prev.map((c, i) => i === idx ? dsl : c))
                    }}
                  />
                )}
                {entryConditions.length > 1 && (
                  <button
                    className="mt-1 text-xs text-red-500 hover:text-red-700"
                    onClick={() => setEntryConditions(prev => prev.filter((_, i) => i !== idx))}
                  >
                    删除此条件
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Exit conditions */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-gray-500 font-medium">出场条件</label>
              <button
                className="text-xs text-blue-600 hover:text-blue-800"
                onClick={() => setExitConditions(prev => [...prev, ''])}
              >
                + 添加条件
              </button>
            </div>
            {exitConditions.map((cond, idx) => (
              <div key={idx} className="mb-2">
                {editorMode === 'ui' ? (
                  <ConditionEditor
                    label={`出场条件 ${idx + 1}`}
                    value={cond}
                    onChange={(dsl) => {
                      setExitConditions(prev => prev.map((c, i) => i === idx ? dsl : c))
                    }}
                  />
                ) : (
                  <RuleConditionEditor
                    label={`出场条件 ${idx + 1}`}
                    value={cond}
                    onChange={(dsl) => {
                      setExitConditions(prev => prev.map((c, i) => i === idx ? dsl : c))
                    }}
                  />
                )}
                {exitConditions.length > 1 && (
                  <button
                    className="mt-1 text-xs text-red-500 hover:text-red-700"
                    onClick={() => setExitConditions(prev => prev.filter((_, i) => i !== idx))}
                  >
                    删除此条件
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Position sizing */}
          <div>
            <label className="text-xs text-gray-500">最大持仓数</label>
            <input type="number" className="input w-full" value={maxPositions}
              onChange={e => setMaxPositions(e.target.value)} min={1} />
          </div>

          {/* Filters */}
          <div>
            <label className="text-xs text-gray-500 font-medium mb-2 block">过滤选项</label>
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={filterST}
                  onChange={e => setFilterST(e.target.checked)} />
                <span className="text-gray-700">排除 ST 股票</span>
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={filterSuspended}
                  onChange={e => setFilterSuspended(e.target.checked)} />
                <span className="text-gray-700">排除停牌股票</span>
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={filterLimitUpDown}
                  onChange={e => setFilterLimitUpDown(e.target.checked)} />
                <span className="text-gray-700">排除涨跌停股票</span>
              </label>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">调仓频率</label>
          <select className="input w-full" value={rebalance} onChange={e => setRebalance(e.target.value)}>
            <option value="1d">每日 (1d)</option>
            <option value="1w">每周 (1w)</option>
            <option value="1mo">每月 (1mo)</option>
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

      {/* Market rule */}
      <div className="border rounded-lg p-3">
        <div className="text-xs font-medium text-gray-600 mb-2">市场规则</div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500">市场</label>
            <select className="input w-full" value={market} onChange={e => setMarket(e.target.value)}>
              <option value="CN">A 股</option>
              <option value="US">美股</option>
              <option value="HK">港股</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500">复权方式</label>
            <select className="input w-full" value={adjType} onChange={e => setAdjType(e.target.value)}>
              <option value="forward">前复权</option>
              <option value="backward">后复权</option>
              <option value="none">不复权</option>
            </select>
          </div>
        </div>
      </div>

      {/* Quick risk config */}
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

        {selectedPolicies.length > 0 && (
          <div className="mt-3 pt-3 border-t space-y-2">
            {selectedPolicies.map(pName => {
              const pInfo = policies?.find(p => p.name === pName)
              if (!pInfo || pInfo.params.length === 0) return null
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

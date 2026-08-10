import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { datasetsApi, riskApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { ConditionEditor } from '@/components/strategies/ConditionEditor'
import { RuleConditionEditor } from '@/components/strategies/RuleConditionEditor'
import { StrategyTemplates, type StrategyTemplate } from '@/components/strategies/StrategyTemplates'
import { FactorSelector } from '@/components/strategies/FactorSelector'
import { FactorWeightTable } from '@/components/strategies/FactorWeightTable'
import { StrategyTemplateManager } from '@/components/strategies/StrategyTemplateManager'
import { MissingFactorConfig } from '@/components/strategies/MissingFactorConfig'
import { GlobalRiskConfig } from '@/components/strategies/GlobalRiskConfig'
import { FactorCorrelationHint } from '@/components/strategies/FactorCorrelationHint'
import { IndicatorParamConfig } from '@/components/strategies/IndicatorParamConfig'

interface StrategyBuilderProps {
  initialConfig: string
  onChange: (json: string) => void
}

export function StrategyBuilder({ initialConfig, onChange }: StrategyBuilderProps) {
  const { t } = useTranslation()
  const parsed = useMemo(() => {
    try { return JSON.parse(initialConfig) } catch { return {} }
  }, [initialConfig])

  const [strategyType, setStrategyType] = useState(parsed.strategy_type ?? 'StaticTopN')
  const [selectedFactors, setSelectedFactors] = useState<string[]>(parsed.factors ?? ['ret_20d', 'vol_20d'])
  const [factorWeights, setFactorWeights] = useState<Record<string, number>>(parsed.factor_weights ?? {})
  const [missingFactorHandling, setMissingFactorHandling] = useState(parsed.missing_factor_handling ?? 'fill_0')
  const [penaltyPerMissing, setPenaltyPerMissing] = useState(String(parsed.penalty_per_missing ?? 0.5))
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
  const [globalRisk, setGlobalRisk] = useState({
    global_stop_loss_pct: parsed.risk_policy_params?.global_stop?.stop_loss_pct ?? null,
    global_take_profit_pct: parsed.risk_policy_params?.global_stop?.take_profit_pct ?? null,
  })
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
  const [indicatorParamOverrides, setIndicatorParamOverrides] = useState<Record<string, Record<string, number>>>({})
  // BreakoutPullback state
  const [bpN, setBpN] = useState(String(parsed.breakout_config?.N ?? 10))
  const [bpStopLossPct, setBpStopLossPct] = useState(String((parsed.breakout_config?.stop_loss_pct ?? 0.08) * 100))
  const [bpTakeProfitMult, setBpTakeProfitMult] = useState(String(parsed.breakout_config?.take_profit_mult ?? 1.15))
  const [bpShrinkRatio, setBpShrinkRatio] = useState(String(parsed.breakout_config?.shrink_ratio ?? 0.85))
  const [bpBigYangGain, setBpBigYangGain] = useState(String((parsed.breakout_config?.big_yang_gain ?? 0.06) * 100))

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
    const config: Record<string, unknown> = {
      strategy_id: parsed.strategy_id ?? 'my_strategy',
      strategy_type: strategyType,
      universe_id: universeId === 'custom' ? 'all' : universeId,
      rebalance_frequency: rebalance,
      top_n: Number(topN) || 10,
      factors: selectedFactors,
      factor_weights: factorWeights,
      missing_factor_handling: missingFactorHandling,
      sizer,
    }
    if (missingFactorHandling === 'risk_penalty') {
      const numericValue = penaltyPerMissing === '' ? NaN : Number(penaltyPerMissing)
      config.penalty_per_missing = Number.isFinite(numericValue) ? numericValue : 0.5
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
    if (strategyType === 'BreakoutPullback') {
      config.breakout_config = {
        N: Number(bpN) || 10,
        stop_loss_pct: (Number(bpStopLossPct) || 8) / 100,
        take_profit_mult: Number(bpTakeProfitMult) || 1.15,
        shrink_ratio: Number(bpShrinkRatio) || 0.85,
        big_yang_gain: (Number(bpBigYangGain) || 6) / 100,
      }
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
        const name = m[1].toUpperCase()  // Normalize to uppercase for consistency
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
      specMap.forEach((params, name) => {
        const overrides = indicatorParamOverrides[name]
        indicatorSpecs.push({ name, params: overrides ? { ...params, ...overrides } : params })
      })
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
    if (globalRisk.global_stop_loss_pct != null || globalRisk.global_take_profit_pct != null) {
      config.risk_policy_params = {
        ...(config.risk_policy_params as Record<string, unknown> ?? {}),
        global_stop: {
          ...(globalRisk.global_stop_loss_pct != null ? { stop_loss_pct: globalRisk.global_stop_loss_pct } : {}),
          ...(globalRisk.global_take_profit_pct != null ? { take_profit_pct: globalRisk.global_take_profit_pct } : {}),
        },
      }
    }
    config.market_rule = { market, adj_type: adjType }
    onChange(JSON.stringify(config, null, 2))
  }, [strategyType, selectedFactors, factorWeights, missingFactorHandling, penaltyPerMissing, topN, rebalance, sizer, sizerParams, selectedPolicies, policyParams, maxPositionPct, maxLeverage, shortN, topSectors, topNPerSector, comboMethod, subStrategyConfigs, universeId, customAssets, quickStopLoss, quickDrawdownBreaker, globalRisk, market, adjType, entryConditions, exitConditions, maxPositions, filterST, filterSuspended, filterLimitUpDown, indicatorParamOverrides])

  // Handle template selection — populate entry/exit conditions
  const handleTemplateSelect = (tpl: StrategyTemplate) => {
    setEntryConditions(tpl.entry.length > 0 ? tpl.entry : [''])
    setExitConditions(tpl.exit.length > 0 ? tpl.exit : [''])
    setShowTemplates(false)
  }

  const selectedSizerInfo = sizers?.find(s => s.name === sizer)

  // Memoize active indicators extraction to avoid re-parsing DSL on every render
  const activeIndicators = useMemo(() => {
    const allDsl = [...entryConditions, ...exitConditions].filter(c => c.trim()).join(' ')
    const specs: { name: string; params: Record<string, number> }[] = []
    const specMap = new Map<string, Record<string, number>>()
    const pattern = /(\w+)\(([^)]*)\)/g
    let m: RegExpExecArray | null
    while ((m = pattern.exec(allDsl)) !== null) {
      const name = m[1].toUpperCase()
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
    // Apply user overrides
    specMap.forEach((params, name) => {
      const overrides = indicatorParamOverrides[name]
      specs.push({ name, params: overrides ? { ...params, ...overrides } : params })
    })
    return specs
  }, [entryConditions, exitConditions, indicatorParamOverrides])

  return (
    <div className="space-y-4 p-4">
      {/* Strategy Type */}
      <div>
        <label className="text-xs text-gray-500 mb-1 block">{t('component.strategies.type')}</label>
        <select className="input w-full" value={strategyType} onChange={e => setStrategyType(e.target.value)}>
          <option value="StaticTopN">StaticTopN — {t('component.strategies.types.StaticTopN')}</option>
          <option value="MLModelStrategy">MLModelStrategy — {t('component.strategies.types.MLModelStrategy')}</option>
          <option value="MultiFactor">MultiFactor — {t('component.strategies.types.MultiFactor')}</option>
          <option value="MarketNeutral">MarketNeutral — {t('component.strategies.types.MarketNeutral')}</option>
          <option value="SectorRotation">SectorRotation — {t('component.strategies.types.SectorRotation')}</option>
          <option value="Combo">Combo — {t('component.strategies.types.Combo')}</option>
          <option value="IndicatorSignal">IndicatorSignal — {t('component.strategies.types.IndicatorSignal')}</option>
          <option value="BreakoutPullback">BreakoutPullback — 突破回踩选股</option>
        </select>
      </div>

      {/* Universe Selector */}
      <div>
        <label className="text-xs text-gray-500 mb-1 block">{t('component.strategies.params.stock_pool')}</label>
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
          <option value="custom">{t('component.strategies.builder.custom_assets_option')}</option>
        </select>
      </div>
      {universeId === 'custom' && (
        <div>
          <label className="text-xs text-gray-500 mb-1 block">{t('component.strategies.builder.custom_assets_label')}</label>
          <input
            className="input w-full"
            value={customAssets}
            onChange={e => setCustomAssets(e.target.value)}
            placeholder="SSE:600036,SZSE:000001,SZSE:300750"
          />
        </div>
      )}

      {/* Factors & Top N */}
      <div className="space-y-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">{t('component.strategies.builder.factor_selection')}</label>
          <FactorSelector
            selected={selectedFactors}
            onChange={setSelectedFactors}
          />
        </div>

        {selectedFactors.length > 0 && (
          <div>
            <label className="text-xs text-gray-500 mb-1 block">{t('component.strategies.builder.factor_weights')}</label>
            <FactorWeightTable
              factors={selectedFactors}
              weights={factorWeights}
              onChange={setFactorWeights}
            />
          </div>
        )}

        {selectedFactors.length >= 2 && (
          <FactorCorrelationHint
            factors={selectedFactors}
            onRemoveFactor={(factor) => {
              setSelectedFactors(prev => prev.filter(f => f !== factor))
              setFactorWeights(prev => {
                const next = { ...prev }
                delete next[factor]
                return next
              })
            }}
          />
        )}

        <StrategyTemplateManager
          currentFactorWeights={factorWeights}
          currentTopN={Number(topN) || 10}
          currentSelectedFactors={selectedFactors}
          onLoad={(weights, newTopN) => {
            // Update selected factors from template keys
            const tplFactors = Object.keys(weights)
            if (tplFactors.length > 0) {
              setSelectedFactors(tplFactors)
            }
            setFactorWeights(weights)
            setTopN(String(newTopN))
          }}
        />

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">{t('component.strategies.builder.top_n')}</label>
            <input type="number" className="input w-full" value={topN} onChange={e => setTopN(e.target.value)} min={1} />
          </div>
          <div>
            <MissingFactorConfig
              value={missingFactorHandling}
              onChange={setMissingFactorHandling}
            />
          </div>
        </div>
        {missingFactorHandling === 'risk_penalty' && (
          <div>
            <label className="text-xs text-gray-500 mb-1 block">{t('component.strategies.builder.penalty_per_missing')}</label>
            <input
              type="number"
              className="input w-full"
              value={penaltyPerMissing}
              onChange={e => setPenaltyPerMissing(e.target.value)}
              min={0}
              step={0.1}
            />
          </div>
        )}
      </div>

      {/* MarketNeutral: short_n */}
      {strategyType === 'MarketNeutral' && (
        <div className="border rounded-lg p-3 bg-blue-50">
          <div className="text-xs font-medium text-gray-600 mb-2">{t('component.strategies.builder.market_neutral_params')}</div>
          <div>
            <label className="text-xs text-gray-500">{t('component.strategies.builder.short_n')}</label>
            <input type="number" className="input w-full" value={shortN}
              onChange={e => setShortN(e.target.value)} min={1} />
          </div>
        </div>
      )}

      {/* SectorRotation params */}
      {strategyType === 'SectorRotation' && (
        <div className="border rounded-lg p-3 bg-blue-50">
          <div className="text-xs font-medium text-gray-600 mb-2">{t('component.strategies.builder.sector_rotation_params')}</div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500">{t('component.strategies.builder.top_sectors')}</label>
              <input type="number" className="input w-full" value={topSectors}
                onChange={e => setTopSectors(e.target.value)} min={1} />
            </div>
            <div>
              <label className="text-xs text-gray-500">{t('component.strategies.builder.top_n_per_sector')}</label>
              <input type="number" className="input w-full" value={topNPerSector}
                onChange={e => setTopNPerSector(e.target.value)} min={1} />
            </div>
          </div>
        </div>
      )}

      {/* Combo params */}
      {strategyType === 'Combo' && (
        <div className="border rounded-lg p-3 bg-blue-50">
          <div className="text-xs font-medium text-gray-600 mb-2">{t('component.strategies.builder.combo_params')}</div>
          <div className="mb-2">
            <label className="text-xs text-gray-500">{t('component.strategies.builder.combo_method')}</label>
            <select className="input w-full" value={comboMethod} onChange={e => setComboMethod(e.target.value)}>
              <option value="equal_weight">{t('component.strategies.builder.combo_equal_weight')}</option>
              <option value="custom">{t('component.strategies.builder.combo_custom')}</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500">{t('component.strategies.builder.sub_strategy_configs')}</label>
            <textarea className="input w-full font-mono text-xs" rows={4}
              value={subStrategyConfigs} onChange={e => setSubStrategyConfigs(e.target.value)}
              placeholder='[{"strategy_type":"StaticTopN","top_n":5,"sort_factor":"ret_20d"},{"strategy_type":"MultiFactor","top_n":5,"sort_factor":"vol_20d"}]' />
          </div>
        </div>
      )}

      {/* BreakoutPullback params */}
      {strategyType === 'BreakoutPullback' && (
        <div className="border rounded-lg p-3 bg-blue-50 space-y-3">
          <div className="text-xs font-medium text-gray-600 mb-2">突破回踩策略参数</div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500">回看窗口 N (天)</label>
              <input type="number" className="input w-full" value={bpN}
                onChange={e => setBpN(e.target.value)} min={2} max={30} />
            </div>
            <div>
              <label className="text-xs text-gray-500">缩量阈值 (%)</label>
              <input type="number" className="input w-full" value={bpShrinkRatio}
                onChange={e => setBpShrinkRatio(e.target.value)} min={50} max={100} step={1} />
            </div>
            <div>
              <label className="text-xs text-gray-500">大阳线涨幅 (%)</label>
              <input type="number" className="input w-full" value={bpBigYangGain}
                onChange={e => setBpBigYangGain(e.target.value)} min={3} max={15} step={0.5} />
            </div>
            <div>
              <label className="text-xs text-gray-500">回撤止损 (%)</label>
              <input type="number" className="input w-full" value={bpStopLossPct}
                onChange={e => setBpStopLossPct(e.target.value)} min={3} max={20} step={1} />
            </div>
            <div>
              <label className="text-xs text-gray-500">止盈倍数 (×MA20)</label>
              <input type="number" className="input w-full" value={bpTakeProfitMult}
                onChange={e => setBpTakeProfitMult(e.target.value)} min={1.05} max={1.5} step={0.05} />
            </div>
          </div>
          <div className="text-xs text-gray-400 mt-1">
            完整参数可在 JSON 模式下编辑（参考 configs/defaults/breakout_pullback.toml）
          </div>
        </div>
      )}

      {/* IndicatorSignal params */}
      {strategyType === 'IndicatorSignal' && (
        <div className="border rounded-lg p-3 bg-blue-50 space-y-4">
          <div className="text-xs font-medium text-gray-600 mb-2">{t('component.strategies.builder.indicator_signal_params')}</div>

          {/* Mode toggle + template button */}
          <div className="flex gap-2 mb-4">
            <button
              className={`text-xs px-3 py-1.5 rounded transition-colors ${editorMode === 'ui' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}`}
              onClick={() => setEditorMode('ui')}
            >
              {t('component.strategies.builder.ui_mode')}
            </button>
            <button
              className={`text-xs px-3 py-1.5 rounded transition-colors ${editorMode === 'code' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 border border-gray-300 hover:bg-gray-50'}`}
              onClick={() => setEditorMode('code')}
            >
              {t('component.strategies.builder.code_mode')}
            </button>
            <button
              className="text-xs px-3 py-1.5 rounded bg-white text-gray-600 border border-gray-300 hover:bg-gray-50 transition-colors"
              onClick={() => setShowTemplates(true)}
            >
              {t('component.strategies.builder.load_template')}
            </button>
          </div>

          {/* Template modal */}
          {showTemplates && (
            <div className="border rounded-lg p-3 bg-white">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-gray-600">{t('component.strategies.builder.select_template')}</span>
                <button
                  className="text-xs text-gray-400 hover:text-gray-600"
                  onClick={() => setShowTemplates(false)}
                >
                  {t('component.strategies.builder.close')}
                </button>
              </div>
              <StrategyTemplates onSelect={handleTemplateSelect} />
            </div>
          )}

          {/* Entry conditions */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-gray-500 font-medium">{t('component.strategies.builder.entry_conditions')}</label>
              <button
                className="text-xs text-blue-600 hover:text-blue-800"
                onClick={() => setEntryConditions(prev => [...prev, ''])}
              >
                {t('component.strategies.builder.add_condition')}
              </button>
            </div>
            {entryConditions.map((cond, idx) => (
              <div key={idx} className="mb-2">
                {editorMode === 'ui' ? (
                  <ConditionEditor
                    label={t('component.strategies.builder.entry_condition_n', { n: idx + 1 })}
                    value={cond}
                    onChange={(dsl) => {
                      setEntryConditions(prev => prev.map((c, i) => i === idx ? dsl : c))
                    }}
                  />
                ) : (
                  <RuleConditionEditor
                    label={t('component.strategies.builder.entry_condition_n', { n: idx + 1 })}
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
                    {t('component.strategies.builder.delete_condition')}
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Exit conditions */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-gray-500 font-medium">{t('component.strategies.builder.exit_conditions')}</label>
              <button
                className="text-xs text-blue-600 hover:text-blue-800"
                onClick={() => setExitConditions(prev => [...prev, ''])}
              >
                {t('component.strategies.builder.add_condition')}
              </button>
            </div>
            {exitConditions.map((cond, idx) => (
              <div key={idx} className="mb-2">
                {editorMode === 'ui' ? (
                  <ConditionEditor
                    label={t('component.strategies.builder.exit_condition_n', { n: idx + 1 })}
                    value={cond}
                    onChange={(dsl) => {
                      setExitConditions(prev => prev.map((c, i) => i === idx ? dsl : c))
                    }}
                  />
                ) : (
                  <RuleConditionEditor
                    label={t('component.strategies.builder.exit_condition_n', { n: idx + 1 })}
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
                    {t('component.strategies.builder.delete_condition')}
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Indicator Param Config */}
          <IndicatorParamConfig
            activeIndicators={activeIndicators}
            onParamChange={(name, key, value) => {
              setIndicatorParamOverrides(prev => ({
                ...prev,
                [name]: { ...(prev[name] ?? {}), [key]: value },
              }))
            }}
            onInsertDSL={(dsl) => {
              setEntryConditions(prev => {
                // Find first empty slot or append
                const idx = prev.findIndex(c => !c.trim())
                if (idx >= 0) {
                  return prev.map((c, i) => i === idx ? dsl : c)
                }
                return [...prev, dsl]
              })
            }}
          />

          {/* Position sizing */}
          <div>
            <label className="text-xs text-gray-500">{t('component.strategies.builder.max_positions_label')}</label>
            <input type="number" className="input w-full" value={maxPositions}
              onChange={e => setMaxPositions(e.target.value)} min={1} />
          </div>

          {/* Filters */}
          <div>
            <label className="text-xs text-gray-500 font-medium mb-2 block">{t('component.strategies.builder.filters_title')}</label>
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={filterST}
                  onChange={e => setFilterST(e.target.checked)} />
                <span className="text-gray-700">{t('component.strategies.builder.exclude_st')}</span>
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={filterSuspended}
                  onChange={e => setFilterSuspended(e.target.checked)} />
                <span className="text-gray-700">{t('component.strategies.builder.exclude_suspended')}</span>
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={filterLimitUpDown}
                  onChange={e => setFilterLimitUpDown(e.target.checked)} />
                <span className="text-gray-700">{t('component.strategies.builder.exclude_limit_up_down')}</span>
              </label>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">{t('component.strategies.params.rebalance_frequency')}</label>
          <select className="input w-full" value={rebalance} onChange={e => setRebalance(e.target.value)}>
            <option value="1d">{t('component.strategies.builder.rebalance_daily')}</option>
            <option value="1w">{t('component.strategies.builder.rebalance_weekly')}</option>
            <option value="1mo">{t('component.strategies.builder.rebalance_monthly')}</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">{t('component.strategies.builder.sizer_label')}</label>
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
          <div className="text-xs font-medium text-gray-600 mb-2">{t('component.strategies.builder.sizer_params')}</div>
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
        <div className="text-xs font-medium text-gray-600 mb-2">{t('component.strategies.builder.risk_limits')}</div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500">{t('component.strategies.builder.max_position_pct')}</label>
            <input type="number" className="input w-full" value={maxPositionPct}
              onChange={e => setMaxPositionPct(e.target.value)} min={0} max={1} step={0.01} />
          </div>
          <div>
            <label className="text-xs text-gray-500">{t('component.strategies.builder.max_leverage')}</label>
            <input type="number" className="input w-full" value={maxLeverage}
              onChange={e => setMaxLeverage(e.target.value)} min={0} max={5} step={0.1} />
          </div>
        </div>
      </div>

      {/* Market rule */}
      <div className="border rounded-lg p-3">
        <div className="text-xs font-medium text-gray-600 mb-2">{t('component.strategies.builder.market_rule')}</div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500">{t('component.strategies.builder.market_label')}</label>
            <select className="input w-full" value={market} onChange={e => setMarket(e.target.value)}>
              <option value="CN">{t('component.strategies.builder.market_cn')}</option>
              <option value="US">{t('page.market.us')}</option>
              <option value="HK">{t('page.market.hk')}</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500">{t('component.strategies.builder.adj_type')}</label>
            <select className="input w-full" value={adjType} onChange={e => setAdjType(e.target.value)}>
              <option value="forward">{t('page.market.adj_forward')}</option>
              <option value="backward">{t('page.market.adj_backward')}</option>
              <option value="none">{t('page.market.adj_none')}</option>
            </select>
          </div>
        </div>
      </div>

      {/* Global stop / take-profit */}
      <GlobalRiskConfig value={globalRisk} onChange={setGlobalRisk} />

      {/* Quick risk config */}
      <div className="border rounded-lg p-3 bg-amber-50 space-y-3">
        <h4 className="text-sm font-medium text-amber-800">{t('component.strategies.quick_risk_params')}</h4>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">
              {t('component.risk.stop_loss')} (%)
              <span className="ml-1 text-gray-400 cursor-help" title={t('component.risk.stop_loss_hint')}>ⓘ</span>
            </label>
            <input
              type="number"
              step={0.5}
              min={0}
              max={50}
              placeholder={t('common.risk_policy.placeholder_disabled')}
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
              {t('component.risk.position_limit')} (%)
              <span className="ml-1 text-gray-400 cursor-help" title={t('component.risk.position_limit_hint')}>ⓘ</span>
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
              placeholder={t('common.unlimited')}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">
              {t('component.risk.drawdown_breaker')} (%)
              <span className="ml-1 text-gray-400 cursor-help" title={t('component.risk.drawdown_breaker_hint')}>ⓘ</span>
            </label>
            <input
              type="number"
              step={1}
              min={0}
              max={50}
              placeholder={t('common.risk_policy.placeholder_disabled')}
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
        <div className="text-xs font-medium text-gray-600 mb-2">{t('component.risk.policies')}</div>
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

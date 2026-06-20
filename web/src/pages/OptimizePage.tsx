import { useState, useEffect, useCallback } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { optimizeApi, mlApi } from '@/lib/api'
import type { OptimizeResult, ConstraintConfig, SectorLimit, FactorExposureLimit, ViewSpec, FrontierResult } from '@/lib/api'
import { useWorkflowStore } from '@/stores/workflowStore'
import { CovarianceCard } from '@/components/optimize/CovarianceCard'
import { OptimizerCard } from '@/components/optimize/OptimizerCard'
import { ConstraintsTab } from '@/components/optimize/ConstraintsTab'
import { ResultsTab } from '@/components/optimize/ResultsTab'
import { RiskBudgetTab } from '@/components/optimize/RiskBudgetTab'
import { EfficientFrontierChart } from '@/components/optimize/EfficientFrontierChart'

type TabKey = 'constraints' | 'results' | 'risk' | 'frontier'

interface SectorEntry {
  label: string
  assets: string
  min: string
  max: string
}

interface FactorEntry {
  name: string
  min: string
  max: string
  loadings: Record<string, string>
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

export function OptimizePage() {
  // ── Tab navigation ────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<TabKey>('constraints')

  // ── Covariance inputs ─────────────────────────────────────────────────
  const [assetIdsText, setAssetIdsText] = useState('')
  const [covMethod, setCovMethod] = useState<'historical' | 'ewma' | 'ledoit_wolf'>('historical')
  const [covWindow, setCovWindow] = useState('252')
  const [covHalflife, setCovHalflife] = useState('63')

  // ── Optimizer inputs ──────────────────────────────────────────────────
  const [optimizer, setOptimizer] = useState<'mean_variance' | 'risk_parity' | 'cost_aware' | 'black_litterman'>('mean_variance')
  const [longOnly, setLongOnly] = useState(true)

  // ── Black-Litterman inputs ─────────────────────────────────────────────
  const [blViews, setBlViews] = useState<ViewSpec[]>([])
  const [blTau, setBlTau] = useState(0.05)
  const [riskFreeRate, setRiskFreeRate] = useState('0')
  const [costRate, setCostRate] = useState('0.001')
  const [turnoverPenalty, setTurnoverPenalty] = useState('0.0005')

  // ── Expected returns ──────────────────────────────────────────────────
  const [expectedReturnsMap, setExpectedReturnsMap] = useState<Record<string, number>>({})

  // ── Advanced constraints state ────────────────────────────────────────
  const [showConstraints, setShowConstraints] = useState(false)
  const [maxTurnover, setMaxTurnover] = useState('')
  const [perAssetBounds, setPerAssetBounds] = useState<Record<string, { min: string; max: string }>>({})
  const [sectorEntries, setSectorEntries] = useState<SectorEntry[]>([])
  const [factorEntries, setFactorEntries] = useState<FactorEntry[]>([])
  const [maxTrackingError, setMaxTrackingError] = useState('')
  const [excludeST, setExcludeST] = useState(false)
  const [excludeSuspended, setExcludeSuspended] = useState(false)
  const [excludeAssetsText, setExcludeAssetsText] = useState('')

  // ── Results ───────────────────────────────────────────────────────────
  const [covResult, setCovResult] = useState<Record<string, Record<string, number>> | null>(null)
  const [optResult, setOptResult] = useState<OptimizeResult | null>(null)
  const [frontierResult, setFrontierResult] = useState<FrontierResult | null>(null)

  // ── Mutations ─────────────────────────────────────────────────────────
  const covMutation = useMutation({
    mutationFn: optimizeApi.covariance,
    onSuccess: (data) => {
      setCovResult(data.covariance)
      setPerAssetBounds({})
      const assets = Object.keys(data.covariance)
      setExpectedReturnsMap(prev => {
        const next: Record<string, number> = {}
        for (const a of assets) next[a] = prev[a] ?? 0
        return next
      })
    },
  })

  const optMutation = useMutation({
    mutationFn: optimizeApi.optimize,
    onSuccess: (data) => {
      setOptResult(data)
      setActiveTab('results')
      toast.success('Optimization complete')
      const { currentWorkflow: wf, updateContext: uc } = useWorkflowStore.getState()
      if (wf === 'optimize') uc({ optimizeResults: data })
      // Fetch frontier data after optimization using the assets from the result
      const assets = data.weights ? Object.keys(data.weights) : []
      if (assets.length > 0) {
        fetchFrontier(assets)
      }
    },
    onError: (err) => { toast.error(`Optimization failed: ${String(err)}`) },
  })

  const frontierMutation = useMutation({
    mutationFn: optimizeApi.getFrontier,
    onSuccess: (data) => {
      setFrontierResult(data)
    },
    onError: (err) => { console.error('Failed to fetch frontier:', err) },
  })

  const fetchFrontier = useCallback((assets: string[]) => {
    frontierMutation.mutate({
      assets,
      risk_free_rate: Number(riskFreeRate) || 0,
      n_points: 50,
    })
  }, [riskFreeRate, frontierMutation.mutate])

  // ── Workflow integration ──────────────────────────────────────────────
  const { currentWorkflow, updateContext } = useWorkflowStore()

  useEffect(() => {
    if (covResult && currentWorkflow === 'optimize') {
      updateContext({ optimizeConfig: { assets: Object.keys(covResult), optimizer } })
    }
  }, [covResult, currentWorkflow, optimizer, updateContext])

  // ── ML predictions ────────────────────────────────────────────────────
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
        if (asset in next && typeof pred === 'number' && !isNaN(pred)) next[asset] = pred
      }
      return next
    })
    toast.success('ML predictions imported')
  }

  // ── Optimize handler ──────────────────────────────────────────────────
  const handleOptimize = () => {
    if (!covResult) return
    const assets = Object.keys(covResult)
    const returns: Record<string, number> = { ...expectedReturnsMap }
    for (const a of assets) {
      if (!(a in returns)) returns[a] = 0
    }

    // Build sector limits
    const sectorMap: Record<string, string> = {}
    const sectorLimits: Record<string, SectorLimit> = {}
    for (const entry of sectorEntries) {
      if (!entry.label.trim()) continue
      const lo = Number(entry.min)
      const hi = Number(entry.max)
      sectorLimits[entry.label.trim()] = {
        min_weight: isNaN(lo) ? 0 : lo / 100,
        max_weight: isNaN(hi) ? 1 : hi / 100,
      }
      for (const a of entry.assets.split(',').map(s => s.trim()).filter(Boolean)) {
        sectorMap[a] = entry.label.trim()
      }
    }

    // Build factor limits
    const factorLimits: Record<string, FactorExposureLimit> = {}
    const factorLoadings: Record<string, Record<string, number>> = {}
    for (const entry of factorEntries) {
      if (!entry.name.trim()) continue
      const lo = Number(entry.min)
      const hi = Number(entry.max)
      factorLimits[entry.name.trim()] = {
        min_exposure: isNaN(lo) ? -1 : lo,
        max_exposure: isNaN(hi) ? 1 : hi,
      }
      for (const [asset, val] of Object.entries(entry.loadings)) {
        const numVal = Number(val)
        if (!isNaN(numVal) && numVal !== 0) {
          if (!factorLoadings[asset]) factorLoadings[asset] = {}
          factorLoadings[asset][entry.name.trim()] = numVal
        }
      }
    }

    // Per-asset bounds
    const minWeights: Record<string, number> = {}
    const maxWeights: Record<string, number> = {}
    for (const [asset, bounds] of Object.entries(perAssetBounds)) {
      if (bounds.min && !isNaN(Number(bounds.min))) minWeights[asset] = Number(bounds.min) / 100
      if (bounds.max && !isNaN(Number(bounds.max))) maxWeights[asset] = Number(bounds.max) / 100
    }

    const excludeAssetsList = excludeAssetsText.split(',').map(s => s.trim()).filter(Boolean)
    const trackingErr = Number(maxTrackingError)

    const constraintConfig: ConstraintConfig = {
      long_only: longOnly,
      min_weights: Object.keys(minWeights).length ? minWeights : undefined,
      max_weights: Object.keys(maxWeights).length ? maxWeights : undefined,
      max_turnover: maxTurnover && !isNaN(Number(maxTurnover)) ? Number(maxTurnover) / 100 : null,
      turnover_penalty: Number(turnoverPenalty) || 0,
      current_weights: {},
      sector_map: Object.keys(sectorMap).length ? sectorMap : undefined,
      sector_limits: Object.keys(sectorLimits).length ? sectorLimits : undefined,
      factor_loadings: Object.keys(factorLoadings).length ? factorLoadings : undefined,
      factor_limits: Object.keys(factorLimits).length ? factorLimits : undefined,
      max_tracking_error: maxTrackingError && !isNaN(trackingErr) ? trackingErr : null,
      benchmark_weights: {},
      exclude_assets: excludeAssetsList.length ? excludeAssetsList : undefined,
      exclude_st: excludeST,
      st_assets: [],
      exclude_suspended: excludeSuspended,
      suspended_assets: [],
    }

    const payload: Parameters<typeof optimizeApi.optimize>[0] = {
      expected_returns: returns,
      covariance: covResult,
      optimizer,
      long_only: longOnly,
      risk_free_rate: Number(riskFreeRate) || 0,
      cost_rate: Number(costRate) || 0.001,
      turnover_penalty: Number(turnoverPenalty) || 0.0005,
      current_weights: {},
      constraint_config: constraintConfig,
    }

    if (optimizer === 'black_litterman') {
      payload.views = blViews
      payload.tau = blTau
    }

    optMutation.mutate(payload)
  }

  // ── Tabs ──────────────────────────────────────────────────────────────
  const tabs: { key: TabKey; label: string }[] = [
    { key: 'constraints', label: '约束配置' },
    { key: 'results', label: '优化结果' },
    { key: 'risk', label: '风险预算' },
    { key: 'frontier', label: '有效前沿' },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">组合优化</h1>

      <CovarianceCard
        assetIdsText={assetIdsText}
        onAssetIdsTextChange={setAssetIdsText}
        covMethod={covMethod}
        onCovMethodChange={setCovMethod}
        covWindow={covWindow}
        onCovWindowChange={setCovWindow}
        covHalflife={covHalflife}
        onCovHalflifeChange={setCovHalflife}
        onCompute={() => {
          const assetIds = assetIdsText.split(',').map(s => s.trim()).filter(Boolean)
          if (assetIds.length < 2) return
          covMutation.mutate({
            asset_ids: assetIds,
            method: covMethod,
            window: Number(covWindow) || 252,
            halflife: Number(covHalflife) || 63,
          })
        }}
        isPending={covMutation.isPending}
        error={covMutation.error}
        covResult={covResult}
      />

      <OptimizerCard
        optimizer={optimizer}
        onOptimizerChange={setOptimizer}
        longOnly={longOnly}
        onLongOnlyChange={setLongOnly}
        riskFreeRate={riskFreeRate}
        onRiskFreeRateChange={setRiskFreeRate}
        costRate={costRate}
        onCostRateChange={setCostRate}
        turnoverPenalty={turnoverPenalty}
        onTurnoverPenaltyChange={setTurnoverPenalty}
        expectedReturnsMap={expectedReturnsMap}
        onExpectedReturnsMapChange={setExpectedReturnsMap}
        mlFetching={mlFetching}
        mlPredictions={mlPredictions}
        onImportMl={handleImportMlPredictions}
        blViews={blViews}
        onBlViewsChange={setBlViews}
        blTau={blTau}
        onBlTauChange={setBlTau}
        onOptimize={handleOptimize}
        isOptimizing={optMutation.isPending}
        optError={optMutation.error}
        hasCovResult={!!covResult}
      >
        {/* Advanced Constraints toggle + ConstraintsTab */}
        <div className="mt-3">
          <button
            onClick={() => setShowConstraints(!showConstraints)}
            className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
          >
            {showConstraints ? '▼' : '▶'} 高级约束配置
          </button>
          {showConstraints && (
            <ConstraintsTab
              covResult={covResult}
              maxTurnover={maxTurnover}
              onMaxTurnoverChange={setMaxTurnover}
              turnoverPenalty={turnoverPenalty}
              onTurnoverPenaltyChange={setTurnoverPenalty}
              maxTrackingError={maxTrackingError}
              onMaxTrackingErrorChange={setMaxTrackingError}
              excludeST={excludeST}
              onExcludeSTChange={setExcludeST}
              excludeSuspended={excludeSuspended}
              onExcludeSuspendedChange={setExcludeSuspended}
              excludeAssetsText={excludeAssetsText}
              onExcludeAssetsTextChange={setExcludeAssetsText}
              perAssetBounds={perAssetBounds}
              onPerAssetBoundsChange={setPerAssetBounds}
              sectorEntries={sectorEntries}
              onSectorEntriesChange={setSectorEntries}
              factorEntries={factorEntries}
              onFactorEntriesChange={setFactorEntries}
            />
          )}
        </div>
      </OptimizerCard>

      {/* ── Results Tabs ────────────────────────────────────────────────── */}
      {(optResult || covResult) && (
        <div className="bg-white rounded-xl shadow-sm border p-5">
          <div className="flex border-b mb-4">
            {tabs.map(tab => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === tab.key
                    ? 'text-brand-600 border-b-2 border-brand-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === 'constraints' && (
            <ConstraintsTab
              covResult={covResult}
              maxTurnover={maxTurnover}
              onMaxTurnoverChange={setMaxTurnover}
              turnoverPenalty={turnoverPenalty}
              onTurnoverPenaltyChange={setTurnoverPenalty}
              maxTrackingError={maxTrackingError}
              onMaxTrackingErrorChange={setMaxTrackingError}
              excludeST={excludeST}
              onExcludeSTChange={setExcludeST}
              excludeSuspended={excludeSuspended}
              onExcludeSuspendedChange={setExcludeSuspended}
              excludeAssetsText={excludeAssetsText}
              onExcludeAssetsTextChange={setExcludeAssetsText}
              perAssetBounds={perAssetBounds}
              onPerAssetBoundsChange={setPerAssetBounds}
              sectorEntries={sectorEntries}
              onSectorEntriesChange={setSectorEntries}
              factorEntries={factorEntries}
              onFactorEntriesChange={setFactorEntries}
            />
          )}

          {activeTab === 'results' && optResult && (
            <ResultsTab result={optResult} optimizer={optimizer} />
          )}

          {activeTab === 'risk' && (
            <RiskBudgetTab
              resultWeights={optResult?.weights}
              covariance={covResult}
            />
          )}

          {activeTab === 'frontier' && frontierResult && (
            <EfficientFrontierChart
              frontierPoints={frontierResult.points}
              optimalPoint={frontierResult.max_sharpe_point}
              minVariancePoint={frontierResult.min_variance_point}
              individualAssets={frontierResult.individual_assets}
              onPointClick={(point) => {
                toast.info(`Selected: ${formatPct(point.expected_return)} return, ${formatPct(point.volatility)} vol, Sharpe ${point.sharpe.toFixed(3)}`)
              }}
            />
          )}

          {activeTab === 'frontier' && !frontierResult && (
            <div className="flex items-center justify-center h-64 text-gray-500">
              {frontierMutation.isPending ? (
                <div className="flex items-center gap-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600" />
                  <span>Computing efficient frontier...</span>
                </div>
              ) : (
                <p>Run an optimization to view the efficient frontier</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

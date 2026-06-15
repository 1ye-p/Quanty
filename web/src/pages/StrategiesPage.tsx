import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useLocation, useSearchParams } from 'react-router-dom'
import { strategiesApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { toast } from 'sonner'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { StrategyTable } from '@/components/strategies/StrategyTable'
import { StrategyForm } from '@/components/strategies/StrategyForm'
import { BacktestRunModal } from '@/components/strategies/BacktestRunModal'

const DEFAULT_CONFIG = JSON.stringify({
  strategy_id: "my_strategy",
  universe: { exchange: ["SSE", "SZSE"], min_liquidity: 1000000 },
  rebalance_frequency: "1d",
  risk_limits: { max_position_pct: 0.10, max_gross_leverage: 1.0 },
  market_rule: { market: "CN", adj_type: "forward" },
  factors: ["ret_20d", "vol_20d"],
  sizer: "equal_weight"
}, null, 2)

export function StrategiesPage() {
  const qc = useQueryClient()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const [editingId, setEditingId] = useState<string | 'new' | null>(null)
  const [configText, setConfigText] = useState(DEFAULT_CONFIG)
  const configTextRef = useRef(configText)
  configTextRef.current = configText
  const [backtestStrategyId, setBacktestStrategyId] = useState<string | null>(null)
  const [backtestConfigText, setBacktestConfigText] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: extendedQueryKeys.strategies.list(),
    queryFn: strategiesApi.list,
  })

  // Handle navigation state (from other pages)
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
      if (prefill.strategy_id) {
        // Will be handled by StrategyForm
      }
      if (prefill.config) setConfigText(prefill.config)
      setEditingId('new')
    }
    if (openBacktest && prefill?.strategy_id && !prefill.config) {
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

  // Pre-fill config when navigating from MLLabPage with URL params
  useEffect(() => {
    const mlModel = searchParams.get('ml_model')
    const strategyType = searchParams.get('strategy_type')
    if (mlModel && strategyType === 'MLModelStrategy') {
      try {
        const config = JSON.parse(configTextRef.current)
        config.strategy_type = 'MLModelStrategy'
        config.model_id = mlModel
        config.feature_set_version = searchParams.get('feature_set_version') || ''
        config.label_name = searchParams.get('target_name') || 'ret_5d'
        setConfigText(JSON.stringify(config, null, 2))
        setEditingId('new')
      } catch { /* ignore parse errors */ }
    }
  }, [searchParams])

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
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">策略配置</h1>
          <p className="page-subtitle">创建和管理量化策略配置（JSON）</p>
        </div>
        <button
          className="btn-primary"
          onClick={() => {
            setEditingId('new')
            setConfigText(DEFAULT_CONFIG)
          }}
        >
          + 新建策略
        </button>
      </div>

      <StrategyTable
        strategies={data?.items ?? []}
        isLoading={isLoading}
        onEdit={openEdit}
        onBacktest={(s) => {
          setBacktestStrategyId(s.strategy_id)
          setBacktestConfigText(s.config_text)
        }}
        onDelete={(id) => setDeleteTarget(id)}
      />

      {editingId && (
        <StrategyForm
          editingId={editingId}
          initialConfig={configText}
          onClose={() => setEditingId(null)}
        />
      )}

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

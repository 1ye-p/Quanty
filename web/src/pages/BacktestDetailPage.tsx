import { NavLink, Outlet, useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { backtestsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { useEffect } from 'react'
import { useWorkflowStore } from '@/stores/workflowStore'

type TabDef = { id: string; label: string; path: string }

const TABS: TabDef[] = [
  { id: 'overview', label: 'Overview', path: '' },
  { id: 'tearsheet', label: 'Tearsheet', path: 'tearsheet' },
  { id: 'overfitting', label: 'Overfitting', path: 'overfitting' },
  { id: 'fills', label: 'Fills', path: 'fills' },
  { id: 'walkforward', label: 'Walk-Forward', path: 'walkforward' },
  { id: 'tca', label: 'TCA', path: 'tca' },
  { id: 'risk', label: 'Risk', path: 'risk' },
  { id: 'calendar', label: 'Calendar', path: 'calendar' },
  { id: 'advanced', label: 'Advanced', path: 'advanced' },
  { id: 'model-compare', label: 'Model Compare', path: 'model-compare' },
  { id: 'feature-importance', label: 'Feature Importance', path: 'feature-importance' },
  { id: 'model-diagnostics', label: 'Model Diagnostics', path: 'model-diagnostics' },
  { id: 'trade-analysis', label: 'Trade Analysis', path: 'trade-analysis' },
]

export function BacktestDetailPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: detail } = useQuery({
    queryKey: queryKeys.backtests.detail(id!),
    queryFn: () => backtestsApi.get(id!),
    enabled: !!id,
  })

  const isWalkForward = detail?.engine === 'walk_forward'
  const visibleTabs = isWalkForward ? TABS : TABS.filter(tab => tab.id !== 'walkforward')

  // Workflow integration: update context when backtest detail loads
  const { currentWorkflow, updateContext } = useWorkflowStore()
  useEffect(() => {
    if (detail && currentWorkflow) {
      updateContext({
        backtestId: id,
        backtestResults: detail.metrics ?? null,
        strategyId: detail.strategy_id,
      })
    }
  }, [detail, id, currentWorkflow])

  if (!id) return null

  return (
    <div>
      {/* Header with back button */}
      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={() => navigate('/backtests')}
          className="text-gray-400 hover:text-gray-600 text-sm"
        >
          Back to list
        </button>
        <h1 className="page-title mb-0">
          {detail?.strategy_id ?? 'Backtest'}
        </h1>
        <span className="font-mono text-xs text-gray-400">{id.slice(0, 12)}...</span>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-1 mb-4 border-b border-gray-200 overflow-x-auto">
        {visibleTabs.map(({ id: tabId, label, path }) => (
          <NavLink
            key={tabId}
            to={path}
            end={path === ''}
            className={({ isActive }) =>
              `px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px whitespace-nowrap ${
                isActive
                  ? 'border-brand-600 text-brand-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`
            }
          >
            {t('page.backtest.tabs.' + tabId)}
          </NavLink>
        ))}
      </div>

      {/* Child route content */}
      <Outlet />
    </div>
  )
}

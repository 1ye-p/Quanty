import { lazy } from 'react'
import { createBrowserRouter } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { NotFoundPage } from '@/pages/NotFoundPage'

// Helper: wrap named-export modules for React.lazy
const named = <T extends Record<string, unknown>>(
  loader: () => Promise<T>,
  name: keyof T,
) => lazy(() => loader().then(m => ({ default: m[name] as React.ComponentType })))

const OverviewPage  = named(() => import('@/pages/OverviewPage'), 'OverviewPage')
const DatasetsPage  = named(() => import('@/pages/DatasetsPage'), 'DatasetsPage')
const BacktestsPage = named(() => import('@/pages/BacktestsPage'), 'BacktestsPage')
const KnowledgePage = named(() => import('@/pages/KnowledgePage'), 'KnowledgePage')
const AdvisorPage   = named(() => import('@/pages/AdvisorPage'), 'AdvisorPage')
const FactorsPage   = named(() => import('@/pages/FactorsPage'), 'FactorsPage')
const StrategiesPage = named(() => import('@/pages/StrategiesPage'), 'StrategiesPage')
const MLLabPage     = named(() => import('@/pages/MLLabPage'), 'MLLabPage')
const NewsPage      = named(() => import('@/pages/NewsPage'), 'NewsPage')
const LivePage      = named(() => import('@/pages/LivePage'), 'LivePage')
const TradingPage   = named(() => import('@/pages/TradingPage'), 'TradingPage')
const OptimizePage  = named(() => import('@/pages/OptimizePage'), 'OptimizePage')
const RiskPage      = named(() => import('@/pages/RiskPage'), 'RiskPage')
const ScoringPage   = named(() => import('@/pages/ScoringPage'), 'ScoringPage')
const AlertsPage    = named(() => import('@/pages/AlertsPage'), 'AlertsPage')
const TasksPage     = named(() => import('@/pages/TasksPage'), 'TasksPage')

export const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <ErrorBoundary>
        <AppLayout />
      </ErrorBoundary>
    ),
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'factors',    element: <FactorsPage /> },
      { path: 'strategies', element: <StrategiesPage /> },
      { path: 'ml',         element: <MLLabPage /> },
      { path: 'backtests',  element: <BacktestsPage /> },
      { path: 'live',       element: <LivePage /> },
      { path: 'trading',    element: <TradingPage /> },
      { path: 'news',       element: <NewsPage /> },
      { path: 'optimize',   element: <OptimizePage /> },
      { path: 'risk',       element: <RiskPage /> },
      { path: 'scoring',    element: <ScoringPage /> },
      { path: 'datasets',   element: <DatasetsPage /> },
      { path: 'knowledge',  element: <KnowledgePage /> },
      { path: 'advisor',    element: <AdvisorPage /> },
      { path: 'alerts',     element: <AlertsPage /> },
      { path: 'tasks',      element: <TasksPage /> },
    ],
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
])

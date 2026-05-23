import { createBrowserRouter } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { OverviewPage } from '@/pages/OverviewPage'
import { DatasetsPage } from '@/pages/DatasetsPage'
import { BacktestsPage } from '@/pages/BacktestsPage'
import { KnowledgePage } from '@/pages/KnowledgePage'
import { AdvisorPage } from '@/pages/AdvisorPage'
import { FactorsPage } from '@/pages/FactorsPage'
import { StrategiesPage } from '@/pages/StrategiesPage'
import { MLLabPage } from '@/pages/MLLabPage'
import { NewsPage } from '@/pages/NewsPage'
import { LivePage } from '@/pages/LivePage'
import { TradingPage } from '@/pages/TradingPage'

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
      { path: 'datasets',   element: <DatasetsPage /> },
      { path: 'knowledge',  element: <KnowledgePage /> },
      { path: 'advisor',    element: <AdvisorPage /> },
    ],
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
])

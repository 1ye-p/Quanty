import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

const ROUTE_LABEL_KEYS: Record<string, string> = {
  factors: 'common.nav.factors',
  strategies: 'common.nav.strategies',
  ml: 'common.nav.ml',
  backtests: 'common.nav.backtests',
  optimize: 'common.nav.optimize',
  risk: 'common.nav.risk',
  scoring: 'common.nav.scoring',
  live: 'common.nav.live',
  trading: 'common.nav.trading',
  news: 'common.nav.news',
  datasets: 'common.nav.datasets',
  knowledge: 'common.nav.knowledge',
  advisor: 'common.nav.advisor',
  alerts: 'common.nav.alerts',
  tasks: 'common.nav.tasks',
  pipeline: 'common.nav.pipeline',
}

export function Breadcrumb() {
  const { t } = useTranslation()
  const location = useLocation()
  const crumbs = location.pathname.split('/').filter(Boolean)

  if (crumbs.length === 0) return null

  return (
    <nav className="flex items-center gap-1 text-xs text-gray-400 mb-4">
      <Link to="/" className="hover:text-gray-600 transition-colors">{t('component.ui.breadcrumb.home')}</Link>
      {crumbs.map((crumb, i) => {
        const isLast = i === crumbs.length - 1
        const to = '/' + crumbs.slice(0, i + 1).join('/')
        const key = ROUTE_LABEL_KEYS[crumb]
        const label = key ? t(key) : crumb
        return (
          <span key={i} className="flex items-center gap-1">
            <span>/</span>
            {isLast ? (
              <span className="text-gray-700 font-medium">
                {label}
              </span>
            ) : (
              <Link to={to} className="hover:text-gray-600 transition-colors">
                {label}
              </Link>
            )}
          </span>
        )
      })}
    </nav>
  )
}

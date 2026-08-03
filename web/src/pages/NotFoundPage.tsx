import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

export function NotFoundPage() {
  const { t } = useTranslation()
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="card max-w-sm w-full text-center">
        <div className="text-6xl font-bold text-gray-200 mb-2">404</div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{t('page.not_found.title')}</h1>
        <p className="text-sm text-gray-500 mb-6">
          {t('page.not_found.description')}
        </p>
        <Link to="/" className="btn-primary inline-block">
          {t('page.not_found.back_home')}
        </Link>
      </div>
    </div>
  )
}

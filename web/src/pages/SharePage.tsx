import { useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { getShareContent } from '@/lib/share'

export function SharePage() {
  const { t } = useTranslation()
  const { shareId } = useParams<{ shareId: string }>()

  const { data, isLoading, error } = useQuery({
    queryKey: ['share', shareId],
    queryFn: () => getShareContent(shareId!),
    enabled: !!shareId,
    retry: false,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        <span className="ml-3 text-gray-500">{t('page.share.loading')}</span>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="text-center py-24">
        <div className="text-4xl mb-4">🔗</div>
        <h1 className="text-xl font-semibold text-gray-800 mb-2">{t('page.share.invalid_title')}</h1>
        <p className="text-sm text-gray-500">{t('page.share.invalid_msg')}</p>
      </div>
    )
  }

  const title = data.type === 'backtest' ? t('page.share.type.backtest') : t('page.share.type.strategy')
  const entries = Object.entries(data.data)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">{t('page.share.title', { type: title })}</h1>
        <p className="page-subtitle">
          {t('page.share.subtitle_id')}: <span className="font-mono">{data.shareId}</span>
          {' · '}
          {t('page.share.created_at', { date: new Date(data.createdAt).toLocaleString('zh-CN') })}
        </p>
      </div>

      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="table-th w-48">{t('page.share.col.field')}</th>
              <th className="table-th">{t('page.share.col.value')}</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([key, value]) => (
              <tr key={key} className="table-row">
                <td className="table-td font-medium text-gray-600">{key}</td>
                <td className="table-td font-mono text-sm break-all">
                  {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value ?? '')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

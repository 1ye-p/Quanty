import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getShareContent } from '@/lib/share'

export function SharePage() {
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
        <span className="ml-3 text-gray-500">加载分享内容...</span>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="text-center py-24">
        <div className="text-4xl mb-4">🔗</div>
        <h1 className="text-xl font-semibold text-gray-800 mb-2">链接无效或已过期</h1>
        <p className="text-sm text-gray-500">该分享链接可能已被删除或超过有效期。</p>
      </div>
    )
  }

  const title = data.type === 'backtest' ? '回测结果' : '策略配置'
  const entries = Object.entries(data.data)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">分享: {title}</h1>
        <p className="page-subtitle">
          分享 ID: <span className="font-mono">{data.shareId}</span>
          {' · '}
          创建于 {new Date(data.createdAt).toLocaleString('zh-CN')}
        </p>
      </div>

      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="table-th w-48">字段</th>
              <th className="table-th">值</th>
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

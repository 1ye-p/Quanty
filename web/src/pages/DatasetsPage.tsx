import { useQuery } from '@tanstack/react-query'
import { datasetsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

export function DatasetsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.datasets.list(100),
    queryFn: () => datasetsApi.list(100),
  })

  if (isLoading) return <p className="text-gray-400">Loading…</p>
  if (error) return <p className="text-red-500">Error: {(error as Error).message}</p>

  return (
    <div>
      <h1 className="page-title">数据集</h1>
      <p className="page-subtitle">共 {data?.total ?? 0} 个版本</p>

      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              {['名称', '频率', '开始', '结束', '资产数', '行数', '来源', '创建时间'].map(h => (
                <th key={h} className="table-th">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!data?.items.length && (
              <tr><td colSpan={8} className="table-td text-center text-gray-400 py-8">暂无数据集</td></tr>
            )}
            {data?.items.map(d => (
              <tr key={d.version_id} className="table-row">
                <td className="table-td font-medium">{d.dataset_name}</td>
                <td className="table-td">{d.frequency}</td>
                <td className="table-td text-gray-500">{d.start_date}</td>
                <td className="table-td text-gray-500">{d.end_date}</td>
                <td className="table-td">{d.asset_count ?? '—'}</td>
                <td className="table-td">{d.row_count?.toLocaleString() ?? '—'}</td>
                <td className="table-td text-gray-500">{d.source}</td>
                <td className="table-td text-gray-400 text-xs">{d.created_at?.slice(0, 16) ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

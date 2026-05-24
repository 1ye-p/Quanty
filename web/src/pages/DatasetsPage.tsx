import { useQuery } from '@tanstack/react-query'
import { datasetsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { DataState } from '@/components/ui/DataState'

export function DatasetsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.datasets.list(100),
    queryFn: () => datasetsApi.list(100),
  })

  return (
    <div>
      <h1 className="page-title">数据集</h1>
      <p className="page-subtitle">共 {data?.total ?? 0} 个版本</p>

      <DataState isLoading={isLoading} error={error} isEmpty={!data?.items.length} emptyText="暂无数据集">
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
      </DataState>
    </div>
  )
}

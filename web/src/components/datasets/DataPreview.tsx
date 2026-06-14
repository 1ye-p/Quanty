import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { datasetsApi } from '@/lib/api'
import { DataState } from '@/components/ui/DataState'

interface DataPreviewProps {
  datasetId: string
}

const PAGE_SIZE = 50

export function DataPreview({ datasetId }: DataPreviewProps) {
  const [page, setPage] = useState(0)
  const offset = page * PAGE_SIZE

  const { data, isLoading, error } = useQuery({
    queryKey: ['datasets', datasetId, 'preview', offset, PAGE_SIZE],
    queryFn: () => datasetsApi.getPreview(datasetId, { offset, limit: PAGE_SIZE }),
    enabled: !!datasetId,
    staleTime: 60_000,
  })

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700">数据预览</h3>
        {data && (
          <span className="text-xs text-gray-500">
            共 {data.total.toLocaleString()} 行
          </span>
        )}
      </div>

      <DataState isLoading={isLoading} error={error} isEmpty={!data?.rows.length} emptyText="暂无数据">
        {data && (
          <>
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    {data.columns.map(col => (
                      <th key={col} className="table-th whitespace-nowrap">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row, i) => (
                    <tr key={i} className="table-row">
                      {data.columns.map(col => (
                        <td key={col} className="table-td whitespace-nowrap font-mono text-xs">
                          {row[col] != null ? String(row[col]) : <span className="text-gray-300">NULL</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">
                第 {page + 1} / {totalPages} 页
              </span>
              <div className="flex gap-2">
                <button
                  className="btn-secondary text-xs"
                  disabled={page === 0}
                  onClick={() => setPage(p => p - 1)}
                >
                  上一页
                </button>
                <button
                  className="btn-secondary text-xs"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage(p => p + 1)}
                >
                  下一页
                </button>
              </div>
            </div>
          </>
        )}
      </DataState>
    </div>
  )
}

import { useState } from 'react'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { backtestsApi } from '@/lib/api'
import { DataTable } from '@/components/ui/DataTable'
import { queryKeys } from '@/lib/queryKeys'

function downloadCsv(rows: Record<string, unknown>[], filename: string) {
  if (rows.length === 0) return
  const headers = Object.keys(rows[0])
  const lines = [
    headers.join(','),
    ...rows.map(row =>
      headers.map(h => {
        const v = row[h]
        const s = v === null || v === undefined ? '' : String(v)
        return s.includes(',') ? `"${s}"` : s
      }).join(','),
    ),
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function BacktestFillsTab() {
  const { id: selectedId } = useParams<{ id: string }>()
  const [fillsPage, setFillsPage] = useState(0)
  const fillsPageSize = 50

  const { data: fillsData } = useQuery({
    queryKey: queryKeys.backtests.fills(selectedId!, fillsPage * fillsPageSize, fillsPageSize),
    queryFn: () => backtestsApi.getFills(selectedId!, fillsPage * fillsPageSize, fillsPageSize),
    enabled: !!selectedId,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  })

  if (!selectedId) return null

  return (
    <div className="space-y-3">
      {fillsData && fillsData.items.length > 0 && (
        <div className="flex justify-end">
          <button
            className="btn-secondary text-sm"
            onClick={() => downloadCsv(
              (fillsData.items as unknown) as Record<string, unknown>[],
              `fills_${selectedId?.slice(0, 8) ?? 'backtest'}.csv`,
            )}
          >
            Export CSV
          </button>
        </div>
      )}

      <DataTable
        data={(fillsData?.items ?? []) as unknown as Record<string, unknown>[]}
        rowKey={(r) => `${r.trade_date}_${r.asset_id}_${r.order_idx ?? ''}`}
        pageSize={fillsPageSize}
        emptyText="No trade records"
        rowClassName={(row: Record<string, unknown>) =>
          row.reason === 'delist_forced_liquidation' ? 'bg-orange-50' : ''
        }
        backendPagination={fillsData ? {
          total: fillsData.total,
          page: fillsPage,
          onPageChange: setFillsPage,
        } : undefined}
        columns={[
          { key: 'trade_date', label: 'Date', sortable: true, width: '100px',
            render: (v) => <span className="text-xs">{String(v ?? '').slice(0, 10)}</span> },
          { key: 'asset_id', label: 'Asset', sortable: true, searchable: true,
            render: (v) => <span className="font-mono text-xs">{String(v)}</span> },
          { key: 'side', label: 'Side', sortable: true, filterable: true, filters: ['buy', 'sell'],
            render: (v) => (
              <span className={`badge ${v === 'buy' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}`}>
                {v === 'buy' ? 'Buy' : 'Sell'}
              </span>
            ) },
          { key: 'qty', label: 'Qty', sortable: true, width: '80px',
            render: (v) => <span className="text-right block">{Number(v).toLocaleString()}</span> },
          { key: 'price', label: 'Price', sortable: true, width: '80px',
            render: (v) => <span className="text-right block">{Number(v).toFixed(2)}</span> },
          { key: 'notional', label: 'Amount', sortable: true, width: '120px',
            render: (v) => <span className="text-right block">{Number(v).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span> },
          { key: 'total_cost', label: 'Cost', sortable: true, width: '80px',
            render: (v) => <span className="text-right block text-gray-500">{Number(v).toFixed(2)}</span> },
          { key: 'reason', label: 'Reason', width: '120px',
            render: (v: unknown) => {
              if (v === 'delist_forced_liquidation') return <span className="text-orange-600 font-medium">Forced Liquidation</span>
              return <span className="text-gray-400">-</span>
            } },
        ]}
      />
    </div>
  )
}

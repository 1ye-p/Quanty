import { useState, useMemo, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { backtestsApi, jobsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { toast } from 'sonner'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { useBacktestCompareStore } from '@/stores/backtestCompareStore'
import {
  LineChart, Line, Legend,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'

export function BacktestsListPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { selectedIds, toggleSelection, clearSelection } = useBacktestCompareStore()

  const [confirmAction, setConfirmAction] = useState<{ type: 'cancel' | 'delete'; runId: string } | null>(null)
  const [page, setPage] = useState(0)
  const pageSize = 20
  const [btSearch, setBtSearch] = useState('')
  const [showCompare, setShowCompare] = useState(false)

  const cancelMutation = useMutation({
    mutationFn: (runId: string) => jobsApi.cancel(runId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['backtests'] }),
    onError: (e: Error) => toast.error(`Cancel failed: ${e.message}`),
  })

  const deleteMutation = useMutation({
    mutationFn: (runId: string) => jobsApi.delete(runId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['backtests'] }),
    onError: (e: Error) => toast.error(`Delete failed: ${e.message}`),
  })

  const { data, isLoading, isFetching } = useQuery({
    queryKey: queryKeys.backtests.list(page * pageSize, pageSize),
    queryFn: () => backtestsApi.list(page * pageSize, pageSize),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      const d = query.state.data
      return d && !d.items.some(r => r.status === 'running' || r.status === 'pending') ? false : 5000
    },
  })

  const { data: compareData, isLoading: compareLoading } = useQuery({
    queryKey: ['backtests', 'compare', selectedIds.join(',')],
    queryFn: () => backtestsApi.compare(selectedIds.join(',')),
    enabled: showCompare && selectedIds.length >= 2,
    staleTime: 60_000,
  })

  const filteredBacktests = useMemo(() => {
    if (!data?.items) return []
    if (!btSearch.trim()) return data.items
    const q = btSearch.toLowerCase()
    return data.items.filter(
      r => r.strategy_id.toLowerCase().includes(q)
        || r.run_id.toLowerCase().includes(q)
        || (r.engine ?? '').toLowerCase().includes(q)
    )
  }, [data, btSearch])

  // Clear search when items change
  useEffect(() => {
    if (btSearch && filteredBacktests.length === 0 && data?.items?.length) {
      // keep search, user might be typing
    }
  }, [btSearch, filteredBacktests, data])

  // NAV series merge for compare chart
  function mergeNavSeries(
    runs: Array<{ run_id: string; nav_series: { date: string; nav: number }[] }>
  ): Array<Record<string, unknown>> {
    const dateMap = new Map<string, Record<string, unknown>>()
    runs.forEach(r => {
      r.nav_series.forEach(({ date, nav }) => {
        if (!dateMap.has(date)) dateMap.set(date, { date })
        dateMap.get(date)![r.run_id] = nav
      })
    })
    return Array.from(dateMap.values()).sort((a, b) =>
      String(a['date']).localeCompare(String(b['date']))
    )
  }

  return (
    <div>
      <h1 className="page-title">Backtests</h1>
      <div className="flex items-center justify-between mb-1">
        <p className="page-subtitle">
          {btSearch
            ? `Found ${filteredBacktests.length} / ${data?.items?.length ?? 0} (current page) - ${data?.total ?? 0} total`
            : `${data?.total ?? 0} records - Click a row to view details`}
        </p>
        <div className="relative">
          <input
            type="text"
            placeholder="Search strategy or run_id..."
            value={btSearch}
            onChange={e => setBtSearch(e.target.value)}
            className="pl-6 pr-6 py-1 text-xs border rounded focus:outline-none focus:ring-1 focus:ring-brand-500 w-44"
          />
          <span className="absolute left-1.5 top-1/2 -translate-y-1/2 text-gray-400 text-xs">Search</span>
          {btSearch && (
            <button onClick={() => setBtSearch('')}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs">X</button>
          )}
        </div>
      </div>

      {/* Run list */}
      <div className="card p-0 overflow-hidden mb-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-600" />
            <span className="ml-2 text-sm text-gray-500">Loading...</span>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="table-th w-10"><span className="sr-only">Select</span></th>
                {['Run ID', 'Strategy', 'Engine', 'Status', 'Start', 'End', 'Actions'].map(h => (
                  <th key={h} className="table-th">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {!filteredBacktests.length && (
                <tr><td colSpan={8} className="table-td text-center text-gray-400 py-8">
                  {isFetching ? 'Loading...' : btSearch ? 'No matching backtests found' : 'No backtest records'}
                </td></tr>
              )}
              {filteredBacktests.map(r => (
                <tr
                  key={r.run_id}
                  className={`table-row ${r.is_running_job ? 'opacity-60' : 'cursor-pointer'}`}
                  onClick={r.is_running_job ? undefined : () => navigate(`/backtests/${r.run_id}`)}
                >
                  <td className="table-td" onClick={e => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      disabled={!!r.is_running_job}
                      checked={selectedIds.includes(r.run_id)}
                      onChange={() => toggleSelection(r.run_id)}
                      className="w-4 h-4 rounded border-gray-300 accent-brand-600 disabled:opacity-40"
                    />
                  </td>
                  <td className="table-td font-mono text-xs">{r.is_running_job ? '-' : `${r.run_id.slice(0, 8)}...`}</td>
                  <td className="table-td font-medium">{r.is_running_job ? <span className="text-blue-600">Submitting...</span> : r.strategy_id}</td>
                  <td className="table-td text-gray-500">
                    {r.is_running_job
                      ? '-'
                      : r.engine === 'walk_forward'
                        ? <span className="px-1.5 py-0.5 text-xs rounded bg-purple-100 text-purple-700 font-medium">WF Summary</span>
                        : <span className="text-gray-500">{r.engine}</span>}
                  </td>
                  <td className="table-td"><StatusBadge status={r.status} /></td>
                  <td className="table-td text-gray-400">{r.started_at?.slice(0, 16) ?? '-'}</td>
                  <td className="table-td text-gray-400">{r.completed_at?.slice(0, 16) ?? '-'}</td>
                  <td className="table-td" onClick={e => e.stopPropagation()}>
                    {(r.status === 'running' || r.status === 'pending') && (
                      <button
                        onClick={() => setConfirmAction({ type: 'cancel', runId: r.run_id })}
                        className="text-red-500 hover:text-red-700 mr-2 text-xs"
                        title="Stop"
                      >Stop</button>
                    )}
                    <button
                      onClick={() => setConfirmAction({ type: 'delete', runId: r.run_id })}
                      className="text-gray-400 hover:text-gray-600 text-xs"
                      title="Delete"
                    >Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {/* Pagination */}
        {data && data.total > pageSize && (
          <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50 text-sm">
            <span className="text-gray-500">{data.total} total</span>
            <div className="flex gap-2">
              <button
                className="px-3 py-1 rounded border bg-white hover:bg-gray-100 disabled:opacity-40"
                disabled={page === 0}
                onClick={() => setPage(p => p - 1)}
              >Previous</button>
              <span className="px-3 py-1 text-gray-600">
                Page {page + 1} / {Math.ceil(data.total / pageSize)}
              </span>
              <button
                className="px-3 py-1 rounded border bg-white hover:bg-gray-100 disabled:opacity-40"
                disabled={(page + 1) * pageSize >= data.total}
                onClick={() => setPage(p => p + 1)}
              >Next</button>
            </div>
          </div>
        )}
      </div>

      {/* Floating compare bar */}
      {selectedIds.length >= 2 && !showCompare && (
        <div className="fixed bottom-6 right-6 z-20 flex items-center gap-2">
          <button
            className="btn-primary shadow-lg flex items-center gap-2 px-5 py-2.5"
            onClick={() => setShowCompare(true)}
          >
            Compare {selectedIds.length} backtests
          </button>
          <button className="btn-secondary text-xs" onClick={clearSelection}>
            Clear
          </button>
        </div>
      )}

      {/* Compare modal */}
      {showCompare && (
        <div className="fixed inset-0 bg-black/40 z-30 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between p-5 border-b flex-shrink-0">
              <h2 className="text-lg font-semibold text-gray-800">
                Backtest Comparison ({selectedIds.length})
              </h2>
              <button onClick={() => setShowCompare(false)} className="text-gray-400 hover:text-gray-700 text-2xl leading-none">X</button>
            </div>

            <div className="overflow-y-auto flex-1 p-5 space-y-6">
              {compareLoading ? (
                <div className="py-12 text-center text-gray-400">Loading...</div>
              ) : compareData ? (
                <>
                  {/* Metrics comparison table */}
                  <div>
                    <h3 className="font-semibold text-gray-700 mb-3">Key Metrics Comparison</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-gray-500 border-b bg-gray-50">
                            <th className="py-2 px-3">Metric</th>
                            {compareData.runs.map(r => (
                              <th key={r.run_id} className="py-2 px-3 text-center min-w-[120px]">
                                <div className="font-semibold text-gray-800 truncate max-w-[120px]" title={r.strategy_id}>
                                  {r.strategy_id}
                                </div>
                                <div className="text-xs text-gray-400 font-mono font-normal">{r.run_id.slice(0, 10)}...</div>
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {([
                            { key: 'sharpe_ratio', label: 'Sharpe Ratio', pct: false, invert: false },
                            { key: 'max_drawdown', label: 'Max Drawdown', pct: true, invert: true },
                            { key: 'total_return', label: 'Total Return', pct: true, invert: false },
                            { key: 'calmar_ratio', label: 'Calmar Ratio', pct: false, invert: false },
                            { key: 'sortino_ratio', label: 'Sortino Ratio', pct: false, invert: false },
                            { key: 'annualized_volatility', label: 'Ann. Volatility', pct: true, invert: true },
                            { key: 'annualized_return', label: 'Ann. Return', pct: true, invert: false },
                            { key: 'win_rate', label: 'Win Rate', pct: true, invert: false },
                          ] as const).map(({ key, label, pct, invert }) => {
                            const vals = compareData.runs.map(r => {
                              const v = r.metrics?.[key]
                              return v !== undefined && v !== null ? Number(v) : NaN
                            })
                            const validVals = vals.filter(v => !isNaN(v))
                            const best = validVals.length
                              ? invert ? Math.min(...validVals) : Math.max(...validVals)
                              : NaN
                            return (
                              <tr key={key} className="border-b hover:bg-gray-50">
                                <td className="py-2 px-3 text-gray-600">{label}</td>
                                {vals.map((v, i) => {
                                  const isBest = !isNaN(v) && v === best
                                  const display = isNaN(v)
                                    ? '-'
                                    : pct ? `${(v * 100).toFixed(2)}%` : v.toFixed(3)
                                  return (
                                    <td
                                      key={compareData.runs[i].run_id}
                                      className={`py-2 px-3 text-center font-mono ${isBest ? 'text-green-600 font-bold' : 'text-gray-700'}`}
                                    >
                                      {display}
                                    </td>
                                  )
                                })}
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* NAV overlay chart */}
                  {compareData.runs.some(r => r.nav_series.length > 0) && (
                    <div>
                      <h3 className="font-semibold text-gray-700 mb-3">NAV Overlay</h3>
                      <ResponsiveContainer width="100%" height={280}>
                        <LineChart
                          data={mergeNavSeries(compareData.runs)}
                          margin={{ top: 4, right: 16, left: -20, bottom: 0 }}
                        >
                          <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd"
                            tickFormatter={v => String(v).slice(5)} />
                          <YAxis tick={{ fontSize: 10 }} />
                          <Tooltip formatter={(v: number) => v.toFixed(4)} />
                          <Legend />
                          {compareData.runs.map((r, i) => {
                            const COLORS = ['#3b82f6','#ef4444','#10b981','#f59e0b','#8b5cf6','#06b6d4']
                            return (
                              <Line
                                key={r.run_id}
                                dataKey={r.run_id}
                                name={r.strategy_id}
                                stroke={COLORS[i % COLORS.length]}
                                dot={false}
                                strokeWidth={2}
                                connectNulls
                              />
                            )
                          })}
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        isOpen={confirmAction !== null}
        title={confirmAction?.type === 'cancel' ? 'Confirm Stop Backtest' : 'Confirm Delete Backtest'}
        message={confirmAction?.type === 'cancel' ? 'Stop this backtest?' : 'Delete this backtest record? This cannot be undone.'}
        confirmLabel={confirmAction?.type === 'cancel' ? 'Stop' : 'Delete'}
        variant="danger"
        onConfirm={() => {
          if (confirmAction) {
            if (confirmAction.type === 'cancel') cancelMutation.mutate(confirmAction.runId)
            else deleteMutation.mutate(confirmAction.runId)
          }
          setConfirmAction(null)
        }}
        onCancel={() => setConfirmAction(null)}
      />
    </div>
  )
}

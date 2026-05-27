import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { datasetsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { DataState } from '@/components/ui/DataState'

export function DatasetsPage() {
  const [selectedVersion, setSelectedVersion] = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.datasets.list(100),
    queryFn: () => datasetsApi.list(100),
  })

  const { data: quality, isLoading: qualityLoading } = useQuery({
    queryKey: ['datasets', 'quality', selectedVersion],
    queryFn: () => datasetsApi.quality(selectedVersion),
    enabled: !!selectedVersion,
    staleTime: 120_000,
  })

  const { data: scheduleStatus, refetch: refetchSchedule } = useQuery({
    queryKey: ['datasets', 'schedule'],
    queryFn: datasetsApi.scheduleStatus,
    refetchInterval: 30_000,
  })

  const triggerMutation = useMutation({
    mutationFn: datasetsApi.triggerIngest,
    onSuccess: () => {
      // Immediate refetch: C2 fix ensures status is already "running" by the time
      // the response returns, so a single refetch shows the correct state immediately.
      refetchSchedule()
    },
  })

  const qualityCards = quality ? [
    {
      label: '总资产数',
      value: quality.stats.n_assets?.toLocaleString() ?? '—',
      icon: '📦',
      warn: false,
    },
    {
      label: '近30日活跃',
      value: quality.stats.recent_assets?.toLocaleString() ?? '—',
      icon: '📡',
      warn: false,
    },
    {
      label: '总行数',
      value: quality.stats.total_rows
        ? `${(quality.stats.total_rows / 1_000_000).toFixed(1)}M`
        : '—',
      icon: '🗄️',
      warn: false,
    },
    {
      label: '价格异常行',
      value: quality.stats.outlier_count?.toLocaleString() ?? '—',
      icon: '⚠️',
      warn: (quality.stats.outlier_count ?? 0) > 1000,
    },
  ] : []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">数据集</h1>
        <p className="page-subtitle">共 {data?.total ?? 0} 个版本 · 点击版本查看数据质量</p>
      </div>

      {/* 调度状态卡片 */}
      {scheduleStatus && (
        <div className={`card flex items-center justify-between ${
          scheduleStatus.last_status === 'error' ? 'border-red-200 bg-red-50' : ''
        }`}>
          <div className="flex items-center gap-3">
            <div>
              <span className="text-sm font-medium text-gray-700">数据调度</span>
              <span className={`ml-2 text-xs px-2 py-0.5 rounded-full ${
                scheduleStatus.last_status === 'running'
                  ? 'bg-blue-100 text-blue-700 animate-pulse'
                  : scheduleStatus.last_status === 'success'
                  ? 'bg-green-100 text-green-700'
                  : scheduleStatus.last_status === 'error'
                  ? 'bg-red-100 text-red-700'
                  : 'bg-gray-100 text-gray-600'
              }`}>
                {scheduleStatus.last_status === 'running' ? '摄取中…'
                  : scheduleStatus.last_status === 'success' ? '● 已启用'
                  : scheduleStatus.last_status === 'error' ? '✗ 上次失败'
                  : '○ 待首次运行'}
              </span>
            </div>
            <div className="text-xs text-gray-500 space-x-3">
              {scheduleStatus.last_data_date && (
                <span>最新数据：<strong className="text-gray-700">{scheduleStatus.last_data_date}</strong></span>
              )}
              {scheduleStatus.last_run && (
                <span>上次运行：{scheduleStatus.last_run.slice(0, 16).replace('T', ' ')}</span>
              )}
              {scheduleStatus.next_run && (
                <span>下次计划：{scheduleStatus.next_run.slice(0, 16).replace('T', ' ')}</span>
              )}
            </div>
          </div>
          <button
            onClick={() => triggerMutation.mutate()}
            disabled={scheduleStatus.last_status === 'running' || triggerMutation.isPending}
            className="btn-secondary text-xs disabled:opacity-40"
          >
            {scheduleStatus.last_status === 'running' ? '摄取中…' : '立即更新'}
          </button>
        </div>
      )}
      {scheduleStatus?.last_error && (
        <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
          错误：{scheduleStatus.last_error}
        </div>
      )}

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
                <tr
                  key={d.version_id}
                  className={`table-row cursor-pointer transition-colors ${
                    selectedVersion === d.version_id
                      ? 'bg-brand-50 border-l-2 border-brand-500'
                      : 'hover:bg-gray-50'
                  }`}
                  onClick={() =>
                    setSelectedVersion(prev => prev === d.version_id ? '' : d.version_id)
                  }
                >
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

      {/* Quality panel */}
      {selectedVersion && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-800">
              数据质量 — {selectedVersion}
            </h2>
            {qualityLoading && (
              <span className="text-xs text-gray-400 flex items-center gap-1">
                <div className="w-3 h-3 border-2 border-gray-300 border-t-brand-500 rounded-full animate-spin" />
                加载中…
              </span>
            )}
          </div>

          {quality && (
            <div className="space-y-5">
              {/* 4 stat cards */}
              <div className="grid grid-cols-4 gap-3">
                {qualityCards.map(c => (
                  <div
                    key={c.label}
                    className={`p-3 rounded-lg border text-center ${
                      c.warn
                        ? 'border-amber-300 bg-amber-50'
                        : 'border-gray-200 bg-gray-50'
                    }`}
                  >
                    <div className="text-2xl mb-1">{c.icon}</div>
                    <div className={`text-xl font-bold ${c.warn ? 'text-amber-700' : 'text-gray-800'}`}>
                      {c.value}
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5">{c.label}</div>
                  </div>
                ))}
              </div>

              {/* Date range + null rate */}
              <div className="flex gap-6 text-sm text-gray-600">
                <span>数据区间：<span className="font-mono text-gray-800">{quality.stats.min_date} ~ {quality.stats.max_date}</span></span>
                <span>空值率：<span className="font-mono text-gray-800">{((quality.stats.null_rate ?? 0) * 100).toFixed(2)}%</span></span>
              </div>

              {/* Daily coverage chart */}
              {quality.daily_coverage.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">日度资产覆盖率（近30天）</h3>
                  <ResponsiveContainer width="100%" height={120}>
                    <LineChart data={quality.daily_coverage} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
                      <XAxis
                        dataKey="trade_date"
                        tick={{ fontSize: 10 }}
                        tickFormatter={v => String(v).slice(5)}
                        interval="preserveStartEnd"
                      />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip
                        formatter={(v: number) => [`${v} 资产`, '每日覆盖']}
                        labelFormatter={v => `日期: ${v}`}
                      />
                      <Line
                        type="monotone"
                        dataKey="n_assets"
                        stroke="#3b82f6"
                        dot={false}
                        strokeWidth={2}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Bottom assets table */}
              {quality.bottom_assets.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">
                    有效天数最少的资产（近90天 Top {Math.min(quality.bottom_assets.length, 10)}）
                  </h3>
                  <div className="overflow-hidden rounded-lg border border-gray-200">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="table-th">Asset ID</th>
                          <th className="table-th">有效天数</th>
                          <th className="table-th">状态</th>
                        </tr>
                      </thead>
                      <tbody>
                        {quality.bottom_assets.slice(0, 10).map(a => (
                          <tr key={a.asset_id} className="table-row">
                            <td className="table-td font-mono">{a.asset_id}</td>
                            <td className="table-td">{a.valid_days}</td>
                            <td className="table-td">
                              <span className={`px-2 py-0.5 rounded text-xs ${
                                a.valid_days < 15
                                  ? 'bg-red-100 text-red-700'
                                  : a.valid_days < 45
                                  ? 'bg-amber-100 text-amber-700'
                                  : 'bg-gray-100 text-gray-600'
                              }`}>
                                {a.valid_days < 15 ? '严重缺失' : a.valid_days < 45 ? '部分缺失' : '正常'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

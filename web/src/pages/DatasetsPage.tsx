import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { datasetsApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'
import { DataState } from '@/components/ui/DataState'
import { DataPreview } from '@/components/datasets/DataPreview'
import { FieldStats } from '@/components/datasets/FieldStats'
import { QualityReport } from '@/components/datasets/QualityReport'
import { AnomalyMarkers } from '@/components/datasets/AnomalyMarkers'

type DetailTab = 'preview' | 'stats' | 'quality' | 'anomalies'

const TABS: { key: DetailTab; label: string }[] = [
  { key: 'preview', label: '数据预览' },
  { key: 'stats', label: '字段统计' },
  { key: 'quality', label: '质量报告' },
  { key: 'anomalies', label: '异常标记' },
]

export function DatasetsPage() {
  const [selectedVersion, setSelectedVersion] = useState('')
  const [activeTab, setActiveTab] = useState<DetailTab>('preview')

  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.datasets.list(100),
    queryFn: () => datasetsApi.list(100),
  })

  const { data: scheduleStatus, refetch: refetchSchedule } = useQuery({
    queryKey: ['datasets', 'schedule'],
    queryFn: datasetsApi.scheduleStatus,
    refetchInterval: 30_000,
  })

  const triggerMutation = useMutation({
    mutationFn: datasetsApi.triggerIngest,
    onSuccess: () => {
      refetchSchedule()
    },
  })

  const handleSelectVersion = (id: string) => {
    setSelectedVersion(prev => {
      if (prev === id) return ''
      setActiveTab('preview')
      return id
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">数据集</h1>
        <p className="page-subtitle">共 {data?.total ?? 0} 个版本 · 点击版本查看详细分析</p>
      </div>

      {/* Schedule status bar */}
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
                {scheduleStatus.last_status === 'running' ? '摄取中...'
                  : scheduleStatus.last_status === 'success' ? '已启用'
                  : scheduleStatus.last_status === 'error' ? '上次失败'
                  : '待首次运行'}
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
            {scheduleStatus.last_status === 'running' ? '摄取中...' : '立即更新'}
          </button>
        </div>
      )}
      {scheduleStatus?.last_error && (
        <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
          错误：{scheduleStatus.last_error}
        </div>
      )}

      {/* Main layout: list + detail */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left: dataset list (4 cols) */}
        <div className="col-span-4">
          <DataState isLoading={isLoading} error={error} isEmpty={!data?.items.length} emptyText="暂无数据集">
            <div className="card p-0 overflow-hidden max-h-[calc(100vh-280px)] overflow-y-auto">
              <table className="w-full">
                <thead className="bg-gray-50 sticky top-0 z-10">
                  <tr>
                    {['名称', '频率', '资产数', '行数'].map(h => (
                      <th key={h} className="table-th text-xs">{h}</th>
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
                      onClick={() => handleSelectVersion(d.version_id)}
                    >
                      <td className="table-td font-medium text-xs">
                        <div className="truncate max-w-[120px]" title={d.dataset_name}>{d.dataset_name}</div>
                        <div className="text-[10px] text-gray-400">{d.frequency}</div>
                      </td>
                      <td className="table-td text-xs text-gray-500">{d.start_date?.slice(5)}</td>
                      <td className="table-td text-xs">{d.asset_count ?? '—'}</td>
                      <td className="table-td text-xs">{d.row_count?.toLocaleString() ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </DataState>
        </div>

        {/* Right: detail tabs (8 cols) */}
        <div className="col-span-8">
          {!selectedVersion ? (
            <div className="card flex items-center justify-center h-64 text-gray-400 text-sm">
              请在左侧选择一个数据集版本
            </div>
          ) : (
            <div className="space-y-4">
              {/* Tab navigation */}
              <div className="flex gap-1 border-b border-gray-200">
                {TABS.map(tab => (
                  <button
                    key={tab.key}
                    className={`px-4 py-2 text-sm font-medium transition-colors -mb-px ${
                      activeTab === tab.key
                        ? 'border-b-2 border-brand-500 text-brand-600'
                        : 'text-gray-500 hover:text-gray-700'
                    }`}
                    onClick={() => setActiveTab(tab.key)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Tab content */}
              <div className="card">
                {activeTab === 'preview' && <DataPreview datasetId={selectedVersion} />}
                {activeTab === 'stats' && <FieldStats datasetId={selectedVersion} />}
                {activeTab === 'quality' && <QualityReport datasetId={selectedVersion} />}
                {activeTab === 'anomalies' && <AnomalyMarkers datasetId={selectedVersion} />}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

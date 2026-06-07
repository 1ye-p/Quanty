import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { mlApi, backtestsApi, scoringApi, jobsApi } from '@/lib/api'
import { elapsedStr } from '@/lib/utils'

interface TaskItem {
  type: string
  id: string
  fullId: string
  status: string
  startedAt?: string | number
  detail: string
}

export function TasksPage() {
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<'all' | 'running' | 'completed' | 'failed'>('all')

  const { data: mlExperiments } = useQuery({
    queryKey: ['tasks', 'ml'],
    queryFn: () => mlApi.experiments(100),
    refetchInterval: 10_000,
  })

  const { data: btRuns } = useQuery({
    queryKey: ['tasks', 'backtests'],
    queryFn: () => backtestsApi.list(0, 100),
    refetchInterval: 10_000,
  })

  const { data: scoringRuns } = useQuery({
    queryKey: ['tasks', 'scoring'],
    queryFn: () => scoringApi.listSnapshots(50),
    refetchInterval: 10_000,
  })

  const cancelMutation = useMutation({
    mutationFn: (jobId: string) => jobsApi.cancel(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => jobsApi.delete(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })

  const allTasks: TaskItem[] = [
    ...(mlExperiments?.items ?? []).map(e => ({
      type: 'ML训练',
      id: e.run_id.slice(0, 10),
      fullId: e.run_id,
      status: e.status,
      startedAt: e.started_at,
      detail: e.trainer_name ?? '',
    })),
    ...(btRuns?.items ?? []).map(r => ({
      type: '回测',
      id: r.run_id.slice(0, 10),
      fullId: r.run_id,
      status: r.status,
      startedAt: r.started_at,
      detail: r.strategy_id ?? '',
    })),
    ...(scoringRuns?.items ?? []).map(s => ({
      type: '截面打分',
      id: s.run_id.slice(0, 10),
      fullId: s.run_id,
      status: s.status,
      startedAt: s.created_at,
      detail: s.config_name ?? '',
    })),
  ]

  const filteredTasks = filter === 'all'
    ? allTasks
    : allTasks.filter(t => {
        if (filter === 'running') return t.status === 'running' || t.status === 'pending'
        if (filter === 'completed') return t.status === 'completed' || t.status === 'done'
        if (filter === 'failed') return t.status === 'failed' || t.status === 'error'
        return true
      })

  const runningCount = allTasks.filter(t => t.status === 'running' || t.status === 'pending').length
  const completedCount = allTasks.filter(t => t.status === 'completed' || t.status === 'done').length
  const failedCount = allTasks.filter(t => t.status === 'failed' || t.status === 'error').length


  const statusColor = (status: string) => {
    switch (status) {
      case 'running': case 'pending': return 'text-blue-600 bg-blue-50'
      case 'completed': case 'done': return 'text-green-600 bg-green-50'
      case 'failed': case 'error': return 'text-red-600 bg-red-50'
      case 'cancelled': return 'text-gray-600 bg-gray-50'
      default: return 'text-gray-600 bg-gray-50'
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">任务管理</h1>
        <p className="text-sm text-gray-500 mt-1">查看和管理所有后台任务</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <button
          onClick={() => setFilter('all')}
          className={`card text-center py-3 cursor-pointer transition-colors ${filter === 'all' ? 'ring-2 ring-brand-500' : 'hover:bg-gray-50'}`}
        >
          <div className="text-2xl font-bold text-gray-800">{allTasks.length}</div>
          <div className="text-xs text-gray-500">全部任务</div>
        </button>
        <button
          onClick={() => setFilter('running')}
          className={`card text-center py-3 cursor-pointer transition-colors ${filter === 'running' ? 'ring-2 ring-blue-500' : 'hover:bg-gray-50'}`}
        >
          <div className="text-2xl font-bold text-blue-600">{runningCount}</div>
          <div className="text-xs text-gray-500">运行中</div>
        </button>
        <button
          onClick={() => setFilter('completed')}
          className={`card text-center py-3 cursor-pointer transition-colors ${filter === 'completed' ? 'ring-2 ring-green-500' : 'hover:bg-gray-50'}`}
        >
          <div className="text-2xl font-bold text-green-600">{completedCount}</div>
          <div className="text-xs text-gray-500">已完成</div>
        </button>
        <button
          onClick={() => setFilter('failed')}
          className={`card text-center py-3 cursor-pointer transition-colors ${filter === 'failed' ? 'ring-2 ring-red-500' : 'hover:bg-gray-50'}`}
        >
          <div className="text-2xl font-bold text-red-600">{failedCount}</div>
          <div className="text-xs text-gray-500">失败</div>
        </button>
      </div>

      {/* Task list */}
      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="table-th">类型</th>
              <th className="table-th">ID</th>
              <th className="table-th">详情</th>
              <th className="table-th">状态</th>
              <th className="table-th">耗时</th>
              <th className="table-th">操作</th>
            </tr>
          </thead>
          <tbody>
            {filteredTasks.length === 0 ? (
              <tr>
                <td colSpan={6} className="table-td text-center text-gray-400 py-12">
                  {filter === 'all' ? '暂无任务记录' : `暂无${filter === 'running' ? '运行中' : filter === 'completed' ? '已完成' : '失败'}的任务`}
                </td>
              </tr>
            ) : (
              filteredTasks.map((task, i) => (
                <tr key={`${task.type}-${task.fullId}-${i}`} className="table-row">
                  <td className="table-td">
                    <span className="text-xs font-medium text-gray-700">{task.type}</span>
                  </td>
                  <td className="table-td font-mono text-xs">{task.id}…</td>
                  <td className="table-td text-sm text-gray-600 truncate max-w-[200px]" title={task.detail}>
                    {task.detail || '—'}
                  </td>
                  <td className="table-td">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(task.status)}`}>
                      {task.status}
                    </span>
                  </td>
                  <td className="table-td text-xs text-gray-500">
                    {elapsedStr(task.startedAt)}
                  </td>
                  <td className="table-td">
                    {(task.status === 'running' || task.status === 'pending') && (
                      <button
                        onClick={() => { if (window.confirm('确定取消该任务？')) cancelMutation.mutate(task.fullId) }}
                        disabled={cancelMutation.isPending}
                        className="text-xs text-red-600 hover:text-red-800 hover:underline disabled:opacity-50"
                      >
                        取消
                      </button>
                    )}
                    {(task.status === 'completed' || task.status === 'done' || task.status === 'failed' || task.status === 'error') && (
                      <button
                        onClick={() => { if (window.confirm('确定删除该任务记录？')) deleteMutation.mutate(task.fullId) }}
                        disabled={deleteMutation.isPending}
                        className="text-xs text-gray-500 hover:text-gray-700 hover:underline disabled:opacity-50"
                      >
                        删除
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

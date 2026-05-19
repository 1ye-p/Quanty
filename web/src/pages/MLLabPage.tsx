import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { mlApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { StatusBadge } from '@/components/ui/StatusBadge'

export function MLLabPage() {
  const [selectedRun, setSelectedRun] = useState<string | null>(null)
  const [jobForm, setJobForm] = useState({ trainer: 'xgb', feature_set_version: '', target_name: 'ret_5d' })

  const { data: experiments, isLoading, refetch } = useQuery({
    queryKey: extendedQueryKeys.ml.experiments(50),
    queryFn: () => mlApi.experiments(50),
  })

  const { data: fi } = useQuery({
    queryKey: extendedQueryKeys.ml.featureImportance(selectedRun ?? ''),
    queryFn: () => mlApi.featureImportance(selectedRun!),
    enabled: !!selectedRun,
  })

  const submitJob = useMutation({
    mutationFn: () => mlApi.submitJob({
      trainer: jobForm.trainer,
      feature_set_version: jobForm.feature_set_version,
      target_name: jobForm.target_name,
    }),
    onSuccess: () => { refetch(); alert('训练 Job 已提交') },
  })

  return (
    <div>
      <h1 className="page-title">机器学习实验室</h1>
      <p className="page-subtitle">XGBoost / LightGBM 训练 · Experiment 对比</p>

      {/* Submit Job */}
      <div className="card mb-6">
        <h2 className="font-semibold text-gray-800 mb-3">提交训练 Job</h2>
        <div className="grid grid-cols-3 gap-3">
          <select className="input" value={jobForm.trainer} onChange={e => setJobForm(f => ({ ...f, trainer: e.target.value }))}>
            <option value="xgb">XGBoost</option>
            <option value="lgbm">LightGBM</option>
          </select>
          <input className="input" placeholder="Feature Set Version" value={jobForm.feature_set_version}
            onChange={e => setJobForm(f => ({ ...f, feature_set_version: e.target.value }))} />
          <input className="input" placeholder="Target（如 ret_5d）" value={jobForm.target_name}
            onChange={e => setJobForm(f => ({ ...f, target_name: e.target.value }))} />
        </div>
        <div className="mt-3 flex justify-end">
          <button className="btn-primary" disabled={submitJob.isPending || !jobForm.feature_set_version}
            onClick={() => submitJob.mutate()}>
            {submitJob.isPending ? '提交中…' : '提交训练'}
          </button>
        </div>
      </div>

      <div className="flex gap-6">
        {/* Experiment list */}
        <div className="flex-1">
          <h2 className="font-semibold text-gray-800 mb-3">实验记录（{experiments?.total ?? 0}）</h2>
          {isLoading && <p className="text-gray-400">Loading…</p>}
          <div className="card p-0 overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  {['Run ID', 'Trainer', '状态', 'RMSE', 'Sharpe', '开始'].map(h => (
                    <th key={h} className="table-th">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {!experiments?.items.length && (
                  <tr><td colSpan={6} className="table-td text-center text-gray-400 py-8">暂无实验记录</td></tr>
                )}
                {experiments?.items.map(r => (
                  <tr key={r.run_id}
                    className={`table-row cursor-pointer ${selectedRun === r.run_id ? 'bg-blue-50' : ''}`}
                    onClick={() => setSelectedRun(r.run_id)}>
                    <td className="table-td font-mono text-xs">{r.run_id.slice(0, 8)}…</td>
                    <td className="table-td">{r.trainer_name || r.params?.trainer_name || '—'}</td>
                    <td className="table-td"><StatusBadge status={r.status?.toLowerCase() ?? 'unknown'} /></td>
                    <td className="table-td">{r.metrics?.rmse?.toFixed(4) ?? '—'}</td>
                    <td className="table-td">{r.metrics?.sharpe?.toFixed(3) ?? '—'}</td>
                    <td className="table-td text-gray-400 text-xs">
                      {typeof r.started_at === 'number' ? new Date(r.started_at).toISOString().slice(0, 16) : String(r.started_at ?? '').slice(0, 16)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Feature importance */}
        {selectedRun && fi && fi.items.length > 0 && (
          <div className="w-80">
            <h2 className="font-semibold text-gray-800 mb-3">特征重要性</h2>
            <div className="card">
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={fi.items.slice(0, 12)} layout="vertical">
                  <XAxis type="number" tick={{ fontSize: 10 }} />
                  <YAxis type="category" dataKey="feature" width={90} tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="importance" fill="#4f63d2" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

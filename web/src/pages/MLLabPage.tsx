import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { mlApi, factorAnalyticsApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { toast } from 'sonner'

export function MLLabPage() {
  const navigate = useNavigate()
  const [selectedRun, setSelectedRun] = useState<string | null>(null)
  const [compareRuns, setCompareRuns] = useState<string[]>([])
  const [jobForm, setJobForm] = useState({ trainer: 'xgb', feature_set_version: '', target_name: 'ret_5d' })
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [walkForward, setWalkForward] = useState({
    enabled: false,
    n_splits: 3,
    gap_days: 5,
    window_type: 'expanding' as 'expanding' | 'sliding',
  })
  const [trainRatio, setTrainRatio] = useState(0.7)
  const [validRatio, setValidRatio] = useState(0.15)
  const [hyperParams, setHyperParams] = useState<Record<string, string>>({})

  const { data: experiments, isLoading, refetch } = useQuery({
    queryKey: extendedQueryKeys.ml.experiments(50),
    queryFn: () => mlApi.experiments(50),
  })

  const { data: fi } = useQuery({
    queryKey: extendedQueryKeys.ml.featureImportance(selectedRun ?? ''),
    queryFn: () => mlApi.featureImportance(selectedRun!),
    enabled: !!selectedRun,
  })

  const comparedExperiments = useMemo(() => {
    if (!experiments?.items || compareRuns.length < 2) return []
    return experiments.items.filter(r => compareRuns.includes(r.run_id))
  }, [experiments, compareRuns])

  const { data: versions } = useQuery({
    queryKey: ['ml', 'versions'],
    queryFn: () => factorAnalyticsApi.versions(),
  })

  const submitJob = useMutation({
    mutationFn: () => {
      const params: Record<string, unknown> = {}
      for (const [key, val] of Object.entries(hyperParams)) {
        if (val !== '') {
          const num = Number(val)
          params[key] = isNaN(num) ? val : num
        }
      }

      return mlApi.submitJob({
        trainer: jobForm.trainer,
        feature_set_version: jobForm.feature_set_version,
        target_name: jobForm.target_name,
        params,
        train_ratio: trainRatio,
        valid_ratio: validRatio,
        ...(walkForward.enabled ? {
          walk_forward: {
            n_splits: walkForward.n_splits,
            gap_days: walkForward.gap_days,
            window_type: walkForward.window_type,
            purge_window: 0,
          },
        } : {}),
      })
    },
    onSuccess: () => { refetch(); toast.success('训练 Job 已提交') },
    onError: (err: Error) => toast.error(`提交失败：${err.message}`),
  })

  return (
    <div>
      <h1 className="page-title">机器学习实验室</h1>
      <p className="page-subtitle">XGBoost / LightGBM 训练 · Experiment 对比</p>

      {/* 三步流程卡片 */}
      <div className="card mb-5">
        <div className="text-xs font-semibold text-gray-500 mb-3 uppercase tracking-wide">ML 研究工作流</div>
        <div className="flex items-center gap-3">
          {[
            { n: 1, label: '确认 Feature Set 版本', done: !!jobForm.feature_set_version },
            { n: 2, label: '提交训练任务', done: (experiments?.items?.length ?? 0) > 0 },
            { n: 3, label: '用模型创建交易策略', done: false },
          ].map((step, idx, arr) => (
            <div key={step.n} className="flex items-center gap-2">
              <div className={`flex items-center gap-1.5 text-sm ${
                step.done ? 'text-green-700 font-medium' : idx === arr.filter(s => s.done).length ? 'text-blue-700 font-medium' : 'text-gray-400'
              }`}>
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
                  step.done ? 'bg-green-600 text-white' : idx === arr.filter(s => s.done).length ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'
                }`}>
                  {step.done ? '✓' : step.n}
                </span>
                {step.label}
              </div>
              {idx < arr.length - 1 && <span className="text-gray-300 text-sm">→</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Submit Job */}
      <div className="card mb-6">
        <h2 className="font-semibold text-gray-800 mb-3">提交训练 Job</h2>
        <div className="grid grid-cols-3 gap-3">
          <select className="input" value={jobForm.trainer} onChange={e => setJobForm(f => ({ ...f, trainer: e.target.value }))}>
            <option value="xgb">XGBoost</option>
            <option value="lgbm">LightGBM</option>
            <option value="xgb_clf">XGBoost Classifier</option>
          </select>
          <select
            className="input"
            value={jobForm.feature_set_version}
            onChange={e => setJobForm(f => ({ ...f, feature_set_version: e.target.value }))}
          >
            <option value="">选择 Feature Set 版本</option>
            {(versions?.items ?? []).map((v: { feature_set_version: string }) => (
              <option key={v.feature_set_version} value={v.feature_set_version}>
                {v.feature_set_version.length > 20 ? v.feature_set_version.slice(0, 20) + '…' : v.feature_set_version}
              </option>
            ))}
          </select>
          <input className="input" placeholder="Target（如 ret_5d）" value={jobForm.target_name}
            onChange={e => setJobForm(f => ({ ...f, target_name: e.target.value }))} />
        </div>

        {/* Advanced config toggle */}
        <button
          className="text-sm text-blue-600 mt-3 hover:underline"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          {showAdvanced ? '收起高级配置' : '展开高级配置（Walk-Forward / 超参数）'}
        </button>

        {showAdvanced && (
          <div className="mt-3 space-y-4 border-t pt-4">
            {/* Data split ratios */}
            <div>
              <label className="block text-sm text-gray-600 mb-1">数据分割比例</label>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs text-gray-500">Train</label>
                  <input type="number" className="input w-full" value={trainRatio}
                    onChange={e => setTrainRatio(Number(e.target.value))} min={0.1} max={0.9} step={0.05} />
                </div>
                <div>
                  <label className="text-xs text-gray-500">Valid</label>
                  <input type="number" className="input w-full" value={validRatio}
                    onChange={e => setValidRatio(Number(e.target.value))} min={0.05} max={0.3} step={0.05} />
                </div>
                <div>
                  <label className="text-xs text-gray-500">Test</label>
                  <input type="number" className="input w-full" disabled
                    value={(1 - trainRatio - validRatio).toFixed(2)} />
                </div>
              </div>
            </div>

            {/* Walk-Forward Config */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                <input
                  type="checkbox"
                  checked={walkForward.enabled}
                  onChange={e => setWalkForward(wf => ({ ...wf, enabled: e.target.checked }))}
                />
                启用 Walk-Forward 滚动训练
              </label>
              {walkForward.enabled && (
                <div className="grid grid-cols-3 gap-3 ml-6">
                  <div>
                    <label className="text-xs text-gray-500">分割数 (n_splits)</label>
                    <input type="number" className="input" min={2} max={10}
                      value={walkForward.n_splits}
                      onChange={e => setWalkForward(wf => ({ ...wf, n_splits: Number(e.target.value) }))} />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500">间隔天数 (gap_days)</label>
                    <input type="number" className="input" min={0} max={30}
                      value={walkForward.gap_days}
                      onChange={e => setWalkForward(wf => ({ ...wf, gap_days: Number(e.target.value) }))} />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500">窗口类型</label>
                    <select className="input"
                      value={walkForward.window_type}
                      onChange={e => setWalkForward(wf => ({ ...wf, window_type: e.target.value as 'expanding' | 'sliding' }))}>
                      <option value="expanding">Expanding（扩展窗口）</option>
                      <option value="sliding">Sliding（滑动窗口）</option>
                    </select>
                  </div>
                </div>
              )}
            </div>

            {/* Hyperparameters */}
            <div>
              <label className="text-sm font-medium text-gray-700 mb-2 block">超参数（可选）</label>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { key: 'learning_rate', label: 'Learning Rate', placeholder: '0.05' },
                  { key: 'max_depth', label: 'Max Depth', placeholder: '6' },
                  { key: 'n_estimators', label: 'N Estimators', placeholder: '300' },
                  { key: 'reg_alpha', label: 'L1 (reg_alpha)', placeholder: '0' },
                  { key: 'reg_lambda', label: 'L2 (reg_lambda)', placeholder: '0' },
                  { key: 'subsample', label: 'Subsample', placeholder: '0.9' },
                ].map(({ key, label, placeholder }) => (
                  <div key={key}>
                    <label className="text-xs text-gray-500">{label}</label>
                    <input className="input" placeholder={placeholder}
                      value={hyperParams[key] ?? ''}
                      onChange={e => setHyperParams(p => ({ ...p, [key]: e.target.value }))} />
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

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
                  {['', 'Run ID', 'Trainer', '状态', 'RMSE', 'Sharpe', '开始', '操作'].map(h => (
                    <th key={h} className="table-th">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {!experiments?.items.length && (
                  <tr><td colSpan={8} className="table-td text-center text-gray-400 py-8">暂无实验记录</td></tr>
                )}
                {experiments?.items.map(r => (
                  <tr key={r.run_id}
                    className={`table-row cursor-pointer ${selectedRun === r.run_id ? 'bg-blue-50' : ''}`}
                    onClick={() => setSelectedRun(r.run_id)}>
                    <td className="table-td" onClick={e => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={compareRuns.includes(r.run_id)}
                        onChange={e => {
                          setCompareRuns(prev =>
                            e.target.checked ? [...prev, r.run_id] : prev.filter(id => id !== r.run_id)
                          )
                        }}
                      />
                    </td>
                    <td className="table-td font-mono text-xs">{r.run_id.slice(0, 8)}…</td>
                    <td className="table-td">{r.trainer_name || r.params?.trainer_name || '—'}</td>
                    <td className="table-td"><StatusBadge status={r.status?.toLowerCase() ?? 'unknown'} /></td>
                    <td className="table-td">{r.metrics?.rmse?.toFixed(4) ?? '—'}</td>
                    <td className="table-td">{r.metrics?.sharpe?.toFixed(3) ?? '—'}</td>
                    <td className="table-td text-gray-400 text-xs">
                      {typeof r.started_at === 'number' ? new Date(r.started_at).toISOString().slice(0, 16) : String(r.started_at ?? '').slice(0, 16)}
                    </td>
                    <td className="table-td" onClick={e => e.stopPropagation()}>
                      {(r.status === 'completed' || r.status === 'done') && r.model_id && (
                        <button
                          className="btn-secondary text-xs"
                          onClick={() => navigate('/strategies', {
                            state: {
                              prefill: {
                                strategy_id: `ml_${r.model_id!.slice(0, 8)}`,
                                config: JSON.stringify({
                                  strategy_type: 'MLModelStrategy',
                                  model_id: r.model_id,
                                  top_n: 10,
                                  label_name: 'ret_5d',
                                }, null, 2),
                              },
                            },
                          })}
                        >
                          创建策略
                        </button>
                      )}
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

      {/* Model comparison panel */}
      {comparedExperiments.length >= 2 && (
        <div className="card mt-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-800">模型对比（{comparedExperiments.length} 个）</h2>
            <button className="text-xs text-gray-400 hover:text-gray-600" onClick={() => setCompareRuns([])}>
              清除选择
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  {['指标', ...comparedExperiments.map(r => r.run_id.slice(0, 8) + '…')].map(h => (
                    <th key={h} className="table-th text-center">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  { label: 'Trainer', key: 'trainer', fmt: (r: typeof comparedExperiments[0]) => r.trainer_name || r.params?.trainer_name || '—' },
                  { label: '状态', key: 'status', fmt: (r: typeof comparedExperiments[0]) => r.status },
                  { label: 'RMSE', key: 'rmse', fmt: (r: typeof comparedExperiments[0]) => r.metrics?.rmse?.toFixed(4) ?? '—' },
                  { label: 'MAE', key: 'mae', fmt: (r: typeof comparedExperiments[0]) => (r.metrics as Record<string, number>)?.mae?.toFixed(4) ?? '—' },
                  { label: 'R²', key: 'r2', fmt: (r: typeof comparedExperiments[0]) => (r.metrics as Record<string, number>)?.r2?.toFixed(4) ?? '—' },
                  { label: 'Directional Acc', key: 'da', fmt: (r: typeof comparedExperiments[0]) => (r.metrics as Record<string, number>)?.directional_accuracy?.toFixed(3) ?? '—' },
                  { label: 'Sharpe', key: 'sharpe', fmt: (r: typeof comparedExperiments[0]) => r.metrics?.sharpe?.toFixed(3) ?? '—' },
                ].map(row => (
                  <tr key={row.key} className="table-row">
                    <td className="table-td font-medium text-gray-600">{row.label}</td>
                    {comparedExperiments.map(r => {
                      const val = row.fmt(r)
                      // Highlight best value for numeric rows
                      const isBest = row.key !== 'trainer' && row.key !== 'status' && (() => {
                        const vals = comparedExperiments.map(e => {
                          const v = row.fmt(e)
                          return v === '—' ? NaN : Number(v)
                        })
                        const numVal = val === '—' ? NaN : Number(val)
                        if (isNaN(numVal)) return false
                        // For RMSE/MAE lower is better, for others higher is better
                        if (row.key === 'rmse' || row.key === 'mae') return numVal === Math.min(...vals.filter(v => !isNaN(v)))
                        return numVal === Math.max(...vals.filter(v => !isNaN(v)))
                      })()
                      return (
                        <td key={r.run_id} className={`table-td text-center ${isBest ? 'font-bold text-green-700' : ''}`}>
                          {val}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

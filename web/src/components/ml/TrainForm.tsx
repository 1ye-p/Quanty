/**
 * ML training form.
 * Handles dataset version, walk-forward config, and job submission.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { mlApi, factorAnalyticsApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { toast } from 'sonner'

interface TrainFormProps {
  groupedModels: { label: string; models: { name: string; display_name: string; engine: string }[] }[]
  onSubmitted?: () => void
}

export function TrainForm({ groupedModels, onSubmitted }: TrainFormProps) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [trainer, setTrainer] = useState('xgb')
  const [featureSetVersion, setFeatureSetVersion] = useState('')
  const [targetName, setTargetName] = useState('ret_5d')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [walkForward, setWalkForward] = useState({
    enabled: false, n_splits: 3, gap_days: 5, window_type: 'expanding' as 'expanding' | 'sliding',
  })
  const [trainRatio, setTrainRatio] = useState(0.7)
  const [validRatio, setValidRatio] = useState(0.15)
  const [hyperParams, setHyperParams] = useState<Record<string, string>>({})

  const { data: versions } = useQuery({
    queryKey: ['ml', 'versions'],
    queryFn: () => factorAnalyticsApi.versions(),
  })

  const submitJob = useMutation({
    mutationFn: () => {
      const params: Record<string, unknown> = {}
      for (const [key, val] of Object.entries(hyperParams)) {
        if (val !== '') { const num = Number(val); params[key] = isNaN(num) ? val : num }
      }
      return mlApi.submitJob({
        trainer,
        feature_set_version: featureSetVersion,
        target_name: targetName,
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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: extendedQueryKeys.ml.experiments(50) })
      toast.success(t('component.ml.train_form.toast_submitted'))
      onSubmitted?.()
    },
    onError: (err: Error) => toast.error(t('component.ml.train_form.toast_failed', { message: err.message })),
  })

  return (
    <div className="space-y-4">
      <div>
        <label className="text-xs text-gray-500 mb-1 block">{t('component.ml.train_form.label_model')}</label>
        <select className="input w-full" value={trainer} onChange={e => setTrainer(e.target.value)}>
          {groupedModels.length > 0 ? (
            groupedModels.map(group => (
              <optgroup key={group.label} label={group.label}>
                {group.models.map(m => (
                  <option key={m.name} value={m.name}>
                    {m.display_name}{m.engine === 'qlib' ? t('component.ml.train_form.qlib_tag') : ''}
                  </option>
                ))}
              </optgroup>
            ))
          ) : (
            <>
              <optgroup label={t('component.ml.train_form.fallback_traditional')}>
                <option value="xgb">XGBoost</option>
                <option value="lgbm">LightGBM</option>
                <option value="catboost">CatBoost</option>
              </optgroup>
              <optgroup label={t('component.ml.train_form.fallback_deep')}>
                <option value="lstm">LSTM</option>
                <option value="transformer">Transformer</option>
              </optgroup>
            </>
          )}
        </select>
      </div>
      <div>
        <label className="text-xs text-gray-500 mb-1 block">{t('component.ml.train_form.label_feature_set')}</label>
        <select className="input w-full" value={featureSetVersion}
          onChange={e => setFeatureSetVersion(e.target.value)}>
          <option value="">{t('component.ml.train_form.ph_select_version')}</option>
          {(versions?.items ?? []).map((v: { feature_set_version: string }) => (
            <option key={v.feature_set_version} value={v.feature_set_version}>
              {v.feature_set_version.length > 20 ? v.feature_set_version.slice(0, 20) + '...' : v.feature_set_version}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="text-xs text-gray-500 mb-1 block">{t('component.ml.train_form.label_target')}</label>
        <input className="input w-full" placeholder={t('component.ml.train_form.ph_target')} value={targetName}
          onChange={e => setTargetName(e.target.value)} />
      </div>

      <button className="text-sm text-blue-600 hover:underline" onClick={() => setShowAdvanced(!showAdvanced)}>
        {showAdvanced ? t('component.ml.train_form.hide_advanced') : t('component.ml.train_form.show_advanced')}
      </button>

      {showAdvanced && (
        <div className="space-y-3 border-t pt-3">
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-xs text-gray-500">{t('component.ml.train_form.label_train')}</label>
              <input type="number" className="input w-full" value={trainRatio}
                onChange={e => setTrainRatio(Number(e.target.value))} min={0.1} max={0.9} step={0.05} />
            </div>
            <div>
              <label className="text-xs text-gray-500">{t('component.ml.train_form.label_valid')}</label>
              <input type="number" className="input w-full" value={validRatio}
                onChange={e => setValidRatio(Number(e.target.value))} min={0.05} max={0.3} step={0.05} />
            </div>
            <div>
              <label className="text-xs text-gray-500">{t('component.ml.train_form.label_test')}</label>
              <input type="number" className="input w-full" disabled value={(1 - trainRatio - validRatio).toFixed(2)} />
            </div>
          </div>

          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={walkForward.enabled}
              onChange={e => setWalkForward(wf => ({ ...wf, enabled: e.target.checked }))} />
            {t('component.ml.train_form.wf_toggle')}
          </label>
          {walkForward.enabled && (
            <div className="grid grid-cols-3 gap-2 ml-4">
              <div>
                <label className="text-xs text-gray-500">{t('component.ml.train_form.wf_splits')}</label>
                <input type="number" className="input" min={2} max={10} value={walkForward.n_splits}
                  onChange={e => setWalkForward(wf => ({ ...wf, n_splits: Number(e.target.value) }))} />
              </div>
              <div>
                <label className="text-xs text-gray-500">{t('component.ml.train_form.wf_gap_days')}</label>
                <input type="number" className="input" min={0} max={30} value={walkForward.gap_days}
                  onChange={e => setWalkForward(wf => ({ ...wf, gap_days: Number(e.target.value) }))} />
              </div>
              <div>
                <label className="text-xs text-gray-500">{t('component.ml.train_form.wf_window')}</label>
                <select className="input" value={walkForward.window_type}
                  onChange={e => setWalkForward(wf => ({ ...wf, window_type: e.target.value as 'expanding' | 'sliding' }))}>
                  <option value="expanding">{t('component.ml.train_form.wf_window_expanding')}</option>
                  <option value="sliding">{t('component.ml.train_form.wf_window_sliding')}</option>
                </select>
              </div>
            </div>
          )}

          <div>
            <label className="text-xs text-gray-500 mb-1 block">{t('component.ml.train_form.label_hyper')}</label>
            <div className="grid grid-cols-2 gap-2">
              {[
                { key: 'learning_rate', label: t('component.ml.train_form.hp_lr'), placeholder: '0.05' },
                { key: 'max_depth', label: t('component.ml.train_form.hp_depth'), placeholder: '6' },
                { key: 'n_estimators', label: t('component.ml.train_form.hp_estimators'), placeholder: '300' },
                { key: 'reg_alpha', label: t('component.ml.train_form.hp_l1'), placeholder: '0' },
              ].map(({ key, label, placeholder }) => (
                <div key={key}>
                  <label className="text-[10px] text-gray-400">{label}</label>
                  <input className="input w-full" placeholder={placeholder}
                    value={hyperParams[key] ?? ''}
                    onChange={e => setHyperParams(p => ({ ...p, [key]: e.target.value }))} />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <button className="btn-primary w-full" disabled={submitJob.isPending || !featureSetVersion}
        onClick={() => submitJob.mutate()}>
        {submitJob.isPending ? t('component.ml.train_form.btn_submitting') : t('component.ml.train_form.btn_start_train')}
      </button>
    </div>
  )
}

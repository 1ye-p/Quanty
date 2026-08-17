/**
 * OptimizationReportModal — 人工审核自动寻优报告的弹窗。
 * 展示：健康检查摘要（baseline vs recent）、寻优参数与新旧指标对比、
 * 过拟合评分（PSR/DSR）。应用新参数需二次确认（安全红线：不自动应用）。
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { strategiesApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import type { OptimizationReport } from '@/lib/types'

interface OptimizationReportModalProps {
  strategyId: string
  onClose: () => void
}

function fmt(v: number | null | undefined, digits = 4): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return v.toFixed(digits)
}

function badgeClass(status: string): string {
  switch (status) {
    case 'needs_review':
      return 'bg-amber-100 text-amber-700 border-amber-300'
    case 'applied':
      return 'bg-green-100 text-green-700 border-green-300'
    case 'failed':
      return 'bg-red-100 text-red-700 border-red-300'
    default: // skipped_healthy / skipped_no_gain
      return 'bg-gray-100 text-gray-600 border-gray-300'
  }
}

/** 策略优化状态角标（healthy=绿 / needs_review=琥珀 / 无报告=无角标） */
export function OptimizationBadge({ status }: { status: string }) {
  const { t } = useTranslation()
  const cls =
    status === 'needs_review'
      ? 'bg-amber-100 text-amber-700'
      : 'bg-green-100 text-green-700'
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${cls}`}>
      {status === 'needs_review'
        ? t('component.optimization_report.badge.needs_review')
        : t('component.optimization_report.badge.healthy')}
    </span>
  )
}

export function OptimizationReportModal({ strategyId, onClose }: OptimizationReportModalProps) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [showApplyConfirm, setShowApplyConfirm] = useState(false)
  const [showDetail, setShowDetail] = useState(false)

  const { data: report, isLoading, error } = useQuery<OptimizationReport>({
    queryKey: extendedQueryKeys.strategies.optimizationReport(strategyId),
    queryFn: () => strategiesApi.optimizationReport(strategyId),
    retry: false,
  })

  const applyMutation = useMutation({
    mutationFn: () =>
      strategiesApi.applyOptimization(strategyId, {
        best_params: report?.best_params ?? {},
        confirm: true,
      }),
    onSuccess: (res) => {
      toast.success(
        t('component.optimization_report.apply.success', { version: res.version_id }),
      )
      setShowApplyConfirm(false)
      qc.invalidateQueries({ queryKey: extendedQueryKeys.strategies.list() })
      qc.invalidateQueries({
        queryKey: extendedQueryKeys.strategies.optimizationReport(strategyId),
      })
      onClose()
    },
    onError: (err: Error) => {
      toast.error(t('component.optimization_report.apply.failed', { message: err.message }))
      setShowApplyConfirm(false)
    },
  })

  const overfit = report?.overfit_check
  const metricKeys = Array.from(
    new Set([
      ...Object.keys(report?.baseline_metrics ?? {}),
      ...Object.keys(report?.candidate_metrics ?? {}),
    ]),
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-xl p-6 max-w-2xl w-full mx-4 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="font-semibold text-gray-900">
              {t('component.optimization_report.title')}
            </h2>
            <p className="text-xs text-gray-400 mt-1">
              {strategyId}
              {report ? ` · ${report.generated_at.slice(0, 19).replace('T', ' ')}` : ''}
            </p>
          </div>
          {report && (
            <span
              className={`px-2 py-1 rounded-full text-xs border font-medium ${badgeClass(report.status)}`}
            >
              {t(`component.optimization_report.status.${report.status}`)}
            </span>
          )}
        </div>

        {isLoading && <p className="text-gray-400">{t('common.loading')}</p>}
        {error && !isLoading && (
          <p className="text-gray-500 text-sm">
            {t('component.optimization_report.no_report')}
          </p>
        )}

        {report && (
          <>
            {/* 健康检查摘要 */}
            <section className="mb-5">
              <h3 className="text-sm font-medium text-gray-700 mb-2">
                {t('component.optimization_report.section.health')}
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                <div className="bg-gray-50 rounded-lg p-2">
                  <div className="text-xs text-gray-400">{t('component.optimization_report.health.baseline_sharpe')}</div>
                  <div className="font-medium">{fmt(report.health?.baseline_sharpe)}</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <div className="text-xs text-gray-400">{t('component.optimization_report.health.recent_sharpe')}</div>
                  <div className="font-medium">{fmt(report.health?.recent_sharpe)}</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <div className="text-xs text-gray-400">{t('component.optimization_report.health.baseline_ic')}</div>
                  <div className="font-medium">{fmt(report.health?.baseline_ic)}</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <div className="text-xs text-gray-400">{t('component.optimization_report.health.recent_ic')}</div>
                  <div className="font-medium">{fmt(report.health?.recent_ic)}</div>
                </div>
              </div>
              {report.reason && (
                <p className="text-xs text-amber-600 mt-2">
                  {t('component.optimization_report.health.reason')}：{report.reason}
                </p>
              )}
            </section>

            {/* 寻优结果：best_params + 指标对比 */}
            {report.best_params && (
              <section className="mb-5">
                <h3 className="text-sm font-medium text-gray-700 mb-2">
                  {t('component.optimization_report.section.params')}
                </h3>
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm mb-3">
                  <pre className="whitespace-pre-wrap break-all">
                    {JSON.stringify(report.best_params, null, 2)}
                  </pre>
                </div>
                {metricKeys.length > 0 && (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-gray-400 border-b">
                        <th className="py-1">{t('component.optimization_report.table.metric')}</th>
                        <th className="py-1">{t('component.optimization_report.table.baseline')}</th>
                        <th className="py-1">{t('component.optimization_report.table.candidate')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {metricKeys.map((k) => (
                        <tr key={k} className="border-b border-gray-100">
                          <td className="py-1.5 text-gray-600">{k}</td>
                          <td className="py-1.5">{fmt(report.baseline_metrics?.[k])}</td>
                          <td className="py-1.5 font-medium">{fmt(report.candidate_metrics?.[k])}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>
            )}

            {/* 过拟合评分 */}
            {overfit && (
              <section className="mb-5">
                <h3 className="text-sm font-medium text-gray-700 mb-2">
                  {t('component.optimization_report.section.overfit')}
                </h3>
                <div className="flex items-center gap-4 text-sm">
                  <span className={overfit.passed ? 'text-green-600' : 'text-red-600'}>
                    {overfit.passed
                      ? `✓ ${t('component.optimization_report.overfit.passed')}`
                      : `✗ ${t('component.optimization_report.overfit.failed')}`}
                  </span>
                  <span className="text-gray-500">
                    PSR: {fmt(overfit.baseline_psr)} → {fmt(overfit.candidate_psr)}
                  </span>
                  <span className="text-gray-500">
                    DSR: {fmt(overfit.baseline_dsr)} → {fmt(overfit.candidate_dsr)}
                  </span>
                </div>
              </section>
            )}

            {/* 操作按钮 */}
            <div className="flex gap-3 justify-end">
              <button className="btn-secondary text-sm" onClick={() => setShowDetail((v) => !v)}>
                {showDetail
                  ? t('component.optimization_report.action.hide_detail')
                  : t('component.optimization_report.action.view_detail')}
              </button>
              <button className="btn-secondary text-sm" onClick={onClose}>
                {t('component.optimization_report.action.dismiss')}
              </button>
              {report.status === 'needs_review' && report.best_params && (
                <button
                  className="btn-primary text-sm"
                  onClick={() => setShowApplyConfirm(true)}
                >
                  {t('component.optimization_report.action.apply')}
                </button>
              )}
            </div>

            {showDetail && (
              <section className="mt-4 pt-4 border-t">
                <h3 className="text-sm font-medium text-gray-700 mb-2">
                  {t('component.optimization_report.section.raw')}
                </h3>
                <pre className="text-xs bg-gray-50 rounded-lg p-3 overflow-x-auto">
                  {JSON.stringify(report, null, 2)}
                </pre>
              </section>
            )}
          </>
        )}
      </div>

      <ConfirmDialog
        isOpen={showApplyConfirm}
        title={t('component.optimization_report.apply.confirm_title')}
        message={t('component.optimization_report.apply.confirm_message')}
        confirmLabel={t('component.optimization_report.apply.confirm_ok')}
        onConfirm={() => applyMutation.mutate()}
        onCancel={() => setShowApplyConfirm(false)}
      />
    </div>
  )
}

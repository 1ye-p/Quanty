import { useState } from 'react'
import { toast } from 'sonner'
import { exportReport, type ExportFormat, type ExportScope } from '@/lib/export/pdf'

interface ExportDialogProps {
  isOpen: boolean
  onClose: () => void
  /** Backtest run ID context (optional) */
  runId?: string
}

export function ExportDialog({ isOpen, onClose, runId }: ExportDialogProps) {
  const [format, setFormat] = useState<ExportFormat>('pdf')
  const [scope, setScope] = useState<ExportScope>('full')
  const [includeCharts, setIncludeCharts] = useState(true)
  const [includeMetrics, setIncludeMetrics] = useState(true)
  const [loading, setLoading] = useState(false)

  if (!isOpen) return null

  async function handleExport() {
    setLoading(true)
    try {
      await exportReport({ format, scope, includeCharts, includeMetrics, runId })
      toast.success('导出成功，文件已下载')
      onClose()
    } catch (err: unknown) {
      toast.error(`导出失败: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-bg-primary rounded-xl shadow-xl w-full max-w-md p-6 space-y-5"
        onClick={e => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-text-primary">导出报告</h2>

        {/* Format */}
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">格式</label>
          <div className="flex gap-3">
            {(['pdf', 'png'] as const).map(f => (
              <button
                key={f}
                onClick={() => setFormat(f)}
                className={`px-4 py-2 rounded-lg border text-sm font-medium transition-colors ${
                  format === f
                    ? 'bg-brand-600 text-white border-brand-600'
                    : 'bg-bg-primary text-text-secondary border-border-primary hover:bg-bg-secondary'
                }`}
              >
                {f.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Scope */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">范围</label>
          <div className="flex gap-3">
            {([
              { value: 'full' as const, label: '完整报告' },
              { value: 'tearsheet' as const, label: 'Tearsheet' },
            ]).map(s => (
              <button
                key={s.value}
                onClick={() => setScope(s.value)}
                className={`px-4 py-2 rounded-lg border text-sm font-medium transition-colors ${
                  scope === s.value
                    ? 'bg-brand-600 text-white border-brand-600'
                    : 'bg-bg-primary text-text-secondary border-border-primary hover:bg-bg-secondary'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Options */}
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={includeCharts}
              onChange={e => setIncludeCharts(e.target.checked)}
              className="rounded border-gray-300"
            />
            包含图表
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={includeMetrics}
              onChange={e => setIncludeMetrics(e.target.checked)}
              className="rounded border-gray-300"
            />
            包含指标表格
          </label>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-2">
          <button onClick={onClose} className="btn-secondary">
            取消
          </button>
          <button onClick={handleExport} disabled={loading} className="btn-primary">
            {loading ? '导出中...' : '导出'}
          </button>
        </div>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { toast } from 'sonner'
import { createShareLink, type ShareLink } from '@/lib/share'

interface ShareDialogProps {
  isOpen: boolean
  onClose: () => void
  /** 'backtest' or 'strategy' */
  type: 'backtest' | 'strategy'
  /** ID of the item to share */
  id: string
}

export function ShareDialog({ isOpen, onClose, type, id }: ShareDialogProps) {
  const [showConfig, setShowConfig] = useState(true)
  const [showResults, setShowResults] = useState(true)
  const [expiresInHours, setExpiresInHours] = useState<number | null>(72)
  const [loading, setLoading] = useState(false)
  const [link, setLink] = useState<ShareLink | null>(null)

  if (!isOpen) return null

  async function handleCreate() {
    setLoading(true)
    try {
      const result = await createShareLink({
        type,
        id,
        permissions: { showConfig, showResults },
        expiresInHours,
      })
      setLink(result)
      toast.success('分享链接已创建')
    } catch (err: unknown) {
      toast.error(`创建失败: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  function handleCopy() {
    if (!link) return
    navigator.clipboard.writeText(link.url).then(
      () => toast.success('链接已复制到剪贴板'),
      () => toast.error('复制失败'),
    )
  }

  function handleClose() {
    setLink(null)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={handleClose}>
      <div
        className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-5"
        onClick={e => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-gray-900">
          分享{type === 'backtest' ? '回测结果' : '策略配置'}
        </h2>

        {!link ? (
          <>
            {/* Permissions */}
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={showConfig}
                  onChange={e => setShowConfig(e.target.checked)}
                  className="rounded border-gray-300"
                />
                显示策略配置
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={showResults}
                  onChange={e => setShowResults(e.target.checked)}
                  className="rounded border-gray-300"
                />
                显示回测结果
              </label>
            </div>

            {/* Expiry */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">有效期</label>
              <select
                value={expiresInHours ?? ''}
                onChange={e => {
                  const v = e.target.value
                  setExpiresInHours(v === '' ? null : Number(v))
                }}
                className="input"
              >
                <option value="24">24 小时</option>
                <option value="72">3 天</option>
                <option value="168">7 天</option>
                <option value="720">30 天</option>
                <option value="">永不过期</option>
              </select>
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-2">
              <button onClick={handleClose} className="btn-secondary">取消</button>
              <button onClick={handleCreate} disabled={loading} className="btn-primary">
                {loading ? '创建中...' : '创建链接'}
              </button>
            </div>
          </>
        ) : (
          <>
            {/* Link created */}
            <div className="bg-gray-50 rounded-lg p-3 break-all text-sm font-mono text-gray-700">
              {link.url}
            </div>
            {link.expiresAt && (
              <p className="text-xs text-gray-400">过期时间: {new Date(link.expiresAt).toLocaleString('zh-CN')}</p>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <button onClick={handleClose} className="btn-secondary">关闭</button>
              <button onClick={handleCopy} className="btn-primary">复制链接</button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

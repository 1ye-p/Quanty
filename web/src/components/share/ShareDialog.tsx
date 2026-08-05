import { useState } from 'react'
import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation()
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
      toast.success(t('component.share_dialog.toast_created'))
    } catch (err: unknown) {
      toast.error(t('component.share_dialog.toast_create_failed', { message: (err as Error).message }))
    } finally {
      setLoading(false)
    }
  }

  function handleCopy() {
    if (!link) return
    navigator.clipboard.writeText(link.url).then(
      () => toast.success(t('component.share_dialog.toast_copied')),
      () => toast.error(t('component.share_dialog.toast_copy_failed')),
    )
  }

  function handleClose() {
    setLink(null)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={handleClose}>
      <div
        className="bg-bg-primary rounded-xl shadow-xl w-full max-w-md p-6 space-y-5"
        onClick={e => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-text-primary">
          {t('component.share_dialog.title', { type: type === 'backtest' ? t('component.share_dialog.type_backtest') : t('component.share_dialog.type_strategy') })}
        </h2>

        {!link ? (
          <>
            {/* Permissions */}
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm text-text-secondary">
                <input
                  type="checkbox"
                  checked={showConfig}
                  onChange={e => setShowConfig(e.target.checked)}
                  className="rounded border-border-primary"
                />
                {t('component.share_dialog.show_config')}
              </label>
              <label className="flex items-center gap-2 text-sm text-text-secondary">
                <input
                  type="checkbox"
                  checked={showResults}
                  onChange={e => setShowResults(e.target.checked)}
                  className="rounded border-border-primary"
                />
                {t('component.share_dialog.show_results')}
              </label>
            </div>

            {/* Expiry */}
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1">{t('component.share_dialog.expiry')}</label>
              <select
                value={expiresInHours ?? ''}
                onChange={e => {
                  const v = e.target.value
                  setExpiresInHours(v === '' ? null : Number(v))
                }}
                className="input"
              >
                <option value="24">{t('component.share_dialog.expiry_24h')}</option>
                <option value="72">{t('component.share_dialog.expiry_72h')}</option>
                <option value="168">{t('component.share_dialog.expiry_168h')}</option>
                <option value="720">{t('component.share_dialog.expiry_720h')}</option>
                <option value="">{t('component.share_dialog.expiry_never')}</option>
              </select>
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-2">
              <button onClick={handleClose} className="btn-secondary">{t('common.cancel')}</button>
              <button onClick={handleCreate} disabled={loading} className="btn-primary">
                {loading ? t('component.share_dialog.creating') : t('component.share_dialog.btn_create_link')}
              </button>
            </div>
          </>
        ) : (
          <>
            {/* Link created */}
            <div className="bg-bg-secondary rounded-lg p-3 break-all text-sm font-mono text-text-secondary">
              {link.url}
            </div>
            {link.expiresAt && (
              <p className="text-xs text-gray-400">{t('component.share_dialog.expires_at', { date: new Date(link.expiresAt).toLocaleString('zh-CN') })}</p>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <button onClick={handleClose} className="btn-secondary">{t('component.share_dialog.close')}</button>
              <button onClick={handleCopy} className="btn-primary">{t('component.share_dialog.btn_copy_link')}</button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

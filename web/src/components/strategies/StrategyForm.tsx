import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { strategiesApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'
import { toast } from 'sonner'
import { StrategyEditor, validateConfig } from './StrategyEditor'
import { StrategyBuilder } from './StrategyBuilder'
import { VersionHistoryPanel } from './VersionHistoryPanel'

interface StrategyFormProps {
  editingId: string | 'new' | null
  initialConfig: string
  onClose: () => void
}

export function StrategyForm({
  editingId,
  initialConfig,
  onClose,
}: StrategyFormProps) {
  const qc = useQueryClient()
  const { t } = useTranslation()
  const [configText, setConfigText] = useState(initialConfig)
  const [newId, setNewId] = useState('')
  const [configError, setConfigError] = useState<string | null>(null)
  const [strategyIdError, setStrategyIdError] = useState<string | null>(null)
  const [editorMode, setEditorMode] = useState<'json' | 'builder'>('json')
  const [rollbackTarget, setRollbackTarget] = useState<string | null>(null)

  // Reset state when editingId changes
  useEffect(() => {
    setConfigText(initialConfig)
    setNewId('')
    setConfigError(null)
    setStrategyIdError(null)
    setEditorMode('json')
  }, [editingId, initialConfig])

  const { data: versions, refetch: refetchVersions } = useQuery({
    queryKey: ['strategies', editingId, 'versions'],
    queryFn: () => strategiesApi.versions(editingId!),
    enabled: !!editingId && editingId !== 'new',
    staleTime: 5_000,
  })

  const createMutation = useMutation({
    mutationFn: () => strategiesApi.create({ strategy_id: newId, config_text: configText }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: extendedQueryKeys.strategies.list() })
      onClose()
    },
    onError: (err: Error) => {
      const msg = err.message
      if (msg.includes('409') || msg.toLowerCase().includes('already exists') || msg.includes('已存在')) {
        setStrategyIdError(t('component.strategies.form.id_exists_error'))
      } else {
        toast.error(t('component.strategies.form.save_failed', { message: msg }))
      }
    },
  })

  const updateMutation = useMutation({
    mutationFn: (id: string) => strategiesApi.update(id, { config_text: configText }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: extendedQueryKeys.strategies.list() })
      qc.invalidateQueries({ queryKey: ['strategies', editingId, 'versions'] })
      onClose()
    },
  })

  const rollbackMutation = useMutation({
    mutationFn: (versionId: string) => strategiesApi.rollback(editingId!, versionId),
    onSuccess: async () => {
      const fresh = await strategiesApi.get(editingId!)
      setConfigText(fresh.config_text)
      refetchVersions()
      toast.success(t('component.strategies.form.rollback_success'))
    },
    onError: (err: Error) => {
      toast.error(t('component.strategies.form.rollback_failed', { message: err.message }))
    },
  })

  if (!editingId) return null

  const isSaving = createMutation.isPending || updateMutation.isPending
  const canSave = editingId === 'new'
    ? newId.trim() && !configError && !isSaving
    : !configError && !isSaving

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-[700px] max-w-[95vw] max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="font-semibold text-gray-900">
            {editingId === 'new'
              ? t('component.strategies.form.title_create')
              : t('component.strategies.form.title_edit', { id: editingId })}
          </h2>
          <button className="text-gray-400 hover:text-gray-600" onClick={onClose}>✕</button>
        </div>
        {editingId === 'new' && (
          <div className="p-4 border-b">
            <input
              className="input"
              placeholder={t('component.strategies.form.id_placeholder')}
              value={newId}
              onChange={e => {
                setNewId(e.target.value)
                setStrategyIdError(null)
              }}
            />
            {strategyIdError && (
              <p className="mt-1 text-xs text-red-600">{strategyIdError}</p>
            )}
          </div>
        )}
        {/* Mode toggle */}
        <div className="flex gap-1 px-4 pt-3">
          <button
            className={`px-3 py-1.5 text-sm rounded-t-lg border-b-2 ${
              editorMode === 'builder' ? 'border-blue-600 text-blue-700 bg-blue-50' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setEditorMode('builder')}
          >
            {t('component.strategies.form.mode_builder')}
          </button>
          <button
            className={`px-3 py-1.5 text-sm rounded-t-lg border-b-2 ${
              editorMode === 'json' ? 'border-blue-600 text-blue-700 bg-blue-50' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setEditorMode('json')}
          >
            {t('component.strategies.form.mode_json')}
          </button>
        </div>
        <div className="flex-1 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 180px)' }}>
          {editorMode === 'builder' ? (
            <StrategyBuilder
              initialConfig={configText}
              onChange={v => {
                setConfigText(v)
                setConfigError(null)
              }}
            />
          ) : (
            <StrategyEditor
              value={configText}
              onChange={v => {
                setConfigText(v)
                setConfigError(validateConfig(v))
              }}
              error={configError}
            />
          )}
        </div>
        {/* Version history (only when editing existing strategy) */}
        {editingId !== 'new' && (
          <div className="mx-4 mb-3 border-t pt-3">
            <VersionHistoryPanel
              versions={versions?.items ?? []}
              onRollback={(versionId) => setRollbackTarget(versionId)}
            />
          </div>
        )}
        <div className="flex justify-end gap-2 p-4 border-t">
          <button className="btn-secondary" onClick={onClose}>{t('common.cancel')}</button>
          <button
            className="btn-primary"
            disabled={!canSave}
            onClick={() => {
              if (editingId === 'new') createMutation.mutate()
              else updateMutation.mutate(editingId)
            }}
          >
            {isSaving ? t('common.saving') : t('common.save')}
          </button>
        </div>
      </div>

      {/* Rollback confirmation */}
      {rollbackTarget && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-[60]">
          <div className="bg-white rounded-lg p-6 max-w-sm w-full mx-4">
            <h3 className="font-semibold mb-2">{t('component.strategies.form.rollback_confirm_title')}</h3>
            <p className="text-sm text-gray-600 mb-4">{t('component.strategies.form.rollback_confirm_body')}</p>
            <div className="flex justify-end gap-2">
              <button className="btn-secondary" onClick={() => setRollbackTarget(null)}>{t('common.cancel')}</button>
              <button
                className="btn-primary"
                onClick={() => {
                  rollbackMutation.mutate(rollbackTarget)
                  setRollbackTarget(null)
                }}
              >
                {t('component.strategies.form.rollback')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

import { useState } from 'react'

interface Version {
  version_id: string
  config_text: string
  config_format: string
  summary: string
  created_at: string
}

interface Props {
  versions: Version[]
  onRollback: (versionId: string) => void
}

export function VersionHistoryPanel({ versions, onRollback }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [diffTarget, setDiffTarget] = useState<string | null>(null)

  if (versions.length === 0) {
    return (
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-2">版本历史</h3>
        <p className="text-sm text-gray-400">暂无版本历史</p>
      </div>
    )
  }

  const diffVersion = versions.find(v => v.version_id === diffTarget)

  return (
    <div className="card">
      <button
        className="flex items-center justify-between w-full"
        onClick={() => setExpanded(!expanded)}
      >
        <h3 className="font-semibold text-gray-800">版本历史 ({versions.length})</h3>
        <span className="text-gray-400">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="mt-3 space-y-2">
          {versions.map(v => {
            const date = new Date(v.created_at)
            const dateStr = date.toLocaleDateString('zh-CN')
            const timeStr = date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
            return (
              <div key={v.version_id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-600">{v.version_id} &middot; {dateStr} {timeStr}</div>
                  <div className="text-sm text-gray-800 truncate">{v.summary}</div>
                </div>
                <div className="flex gap-2 ml-3">
                  <button
                    className="text-xs text-brand-600 hover:underline"
                    onClick={() => setDiffTarget(diffTarget === v.version_id ? null : v.version_id)}
                  >
                    查看
                  </button>
                  <button
                    className="text-xs text-orange-600 hover:underline"
                    onClick={() => onRollback(v.version_id)}
                  >
                    回滚
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {diffVersion && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setDiffTarget(null)}>
          <div className="bg-white rounded-lg p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h3 className="font-semibold mb-3">版本配置</h3>
            <pre className="text-xs bg-gray-50 p-3 rounded overflow-x-auto">
              {(() => { try { return JSON.stringify(JSON.parse(diffVersion.config_text), null, 2) } catch { return diffVersion.config_text } })()}
            </pre>
            <div className="mt-4 flex justify-end">
              <button className="btn-secondary" onClick={() => setDiffTarget(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

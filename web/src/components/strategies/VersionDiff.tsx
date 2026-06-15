import { DiffEditor } from '@monaco-editor/react'

interface Version {
  version_id: string
  config_text: string
  summary: string
  created_at: string
}

interface VersionDiffProps {
  oldVersion: Version
  newVersion: Version
  onClose: () => void
}

export function VersionDiff({ oldVersion, newVersion, onClose }: VersionDiffProps) {
  const formatConfig = (text: string) => {
    try {
      return JSON.stringify(JSON.parse(text), null, 2)
    } catch {
      return text
    }
  }

  const oldContent = formatConfig(oldVersion.config_text)
  const newContent = formatConfig(newVersion.config_text)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-lg w-4/5 h-4/5 flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b">
          <h3 className="font-medium text-gray-800">
            版本对比: {oldVersion.version_id} → {newVersion.version_id}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg">
            ✕
          </button>
        </div>

        {/* Diff Editor */}
        <div className="flex-1 overflow-hidden">
          <DiffEditor
            original={oldContent}
            modified={newContent}
            language="json"
            options={{
              readOnly: true,
              minimap: { enabled: false },
              fontSize: 14,
            }}
          />
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 p-4 border-t">
          <button onClick={onClose} className="btn-secondary">
            关闭
          </button>
        </div>
      </div>
    </div>
  )
}

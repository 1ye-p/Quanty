/**
 * Monaco JSON editor for strategy config with error validation.
 * Lazy-loads Monaco to reduce initial bundle size.
 */
import { lazy, Suspense } from 'react'
const Editor = lazy(() => import('@monaco-editor/react'))

interface StrategyEditorProps {
  value: string
  onChange: (value: string) => void
  error?: string | null
}

export function StrategyEditor({ value, onChange, error }: StrategyEditorProps) {
  return (
    <div className="flex flex-col h-full">
      <Suspense fallback={
        <div className="h-[400px] bg-gray-50 animate-pulse rounded p-4 space-y-2">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="h-3 bg-gray-200 rounded" style={{ width: `${60 + Math.random() * 30}%` }} />
          ))}
        </div>
      }>
        <Editor
          height="400px"
          language="json"
          value={value}
          onChange={v => onChange(v ?? '')}
          options={{ minimap: { enabled: false }, fontSize: 13, scrollBeyondLastLine: false }}
        />
      </Suspense>
      {error && (
        <p className="mt-1 px-4 text-xs text-red-600">{error}</p>
      )}
    </div>
  )
}

/** Validate JSON config text. Returns error message or null. */
export function validateConfig(text: string): string | null {
  if (!text.trim()) return null
  try {
    JSON.parse(text)
    return null
  } catch (e) {
    return `JSON format error: ${(e as Error).message}`
  }
}

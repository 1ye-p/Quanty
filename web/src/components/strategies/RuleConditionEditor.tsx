/**
 * RuleConditionEditor — Monaco editor with DSL syntax highlighting for strategy rules.
 *
 * Combines a Monaco editor (with syntax highlighting, auto-completion, and validation)
 * with a toggle to switch to the visual ConditionEditor. Loads templates from
 * StrategyTemplates for quick starts.
 */
import { useState, useEffect, useCallback, useRef, lazy, Suspense } from 'react'
import type { editor as editorTypes } from 'monaco-editor'
import { useQuery } from '@tanstack/react-query'
import {
  CONDITION_DSL_LANG_ID,
  CONDITION_DSL_LANG,
  CONDITION_DSL_COMPLETIONS,
  CONDITION_DSL_THEME,
  buildDynamicCompletions,
} from './ConditionDSLHighlight'
import { indicatorsApi } from '@/lib/api/indicators'
import { ConditionEditor } from './ConditionEditor'
import { StrategyTemplates, type StrategyTemplate } from './StrategyTemplates'
import { IndicatorReferencePanel } from '@/components/indicators/IndicatorReferencePanel'

const MonacoEditor = lazy(() => import('@monaco-editor/react'))

// ── Types ──────────────────────────────────────────────────────────────────

interface RuleConditionEditorProps {
  /** Label like "买入条件" or "卖出条件" */
  label: string
  /** DSL string value */
  value: string
  /** Callback when DSL changes */
  onChange: (dsl: string) => void
  /** Optional asset ID for hit-count preview */
  assetId?: string
}

// ── Lightweight DSL validator ──────────────────────────────────────────────

interface DslDiagnostic {
  message: string
  line: number
  column: number
}

function validateDsl(dsl: string): DslDiagnostic[] {
  if (!dsl.trim()) return []

  const errors: DslDiagnostic[] = []

  // Check balanced parentheses
  let depth = 0
  for (let i = 0; i < dsl.length; i++) {
    if (dsl[i] === '(') depth++
    if (dsl[i] === ')') depth--
    if (depth < 0) {
      errors.push({ message: 'Unmatched closing parenthesis', line: 1, column: i + 1 })
      return errors
    }
  }
  if (depth > 0) {
    errors.push({ message: 'Unmatched opening parenthesis', line: 1, column: dsl.length })
  }

  // Check that comparisons have two sides
  const tokens = dsl.split(/\s+/)
  for (let i = 0; i < tokens.length; i++) {
    if (/^(>=|<=|!=|==|>|<)$/.test(tokens[i])) {
      if (i === 0 || i === tokens.length - 1) {
        errors.push({ message: `Operator "${tokens[i]}" needs operands on both sides`, line: 1, column: 0 })
      }
    }
    if (/^crosses_above|crosses_below$/.test(tokens[i])) {
      if (i === 0 || i === tokens.length - 1) {
        errors.push({ message: `"${tokens[i]}" needs operands on both sides`, line: 1, column: 0 })
      }
    }
  }

  // Check for unknown keywords
  const knownKeywords = new Set([
    'AND', 'OR', 'NOT', 'for', 'within', 'after', 'bars',
    'crosses_above', 'crosses_below',
    'rsi', 'sma', 'ema', 'wma', 'macd', 'macd_signal', 'macd_hist',
    'bb_upper', 'bb_lower', 'bb_mid', 'atr', 'kdj_k', 'kdj_d', 'kdj_j',
    'adx', 'cci', 'stoch_k', 'stoch_d', 'williams_r', 'roc', 'momentum',
    'obv', 'mfi', 'volume_sma', 'volume_ratio',
    'close', 'open', 'high', 'low', 'volume',
  ])

  for (const tok of tokens) {
    const clean = tok.replace(/[(),]/g, '')
    if (!clean || /^(>=|<=|!=|==|>|<)$/.test(clean)) continue
    if (/^\d+(\.\d+)?$/.test(clean)) continue
    if (knownKeywords.has(clean)) continue
    // Could be a function with params — check if it ends with '('
    if (/\($/.test(tok)) continue
    // Could be a number parameter inside parens
    if (/^\d+(\.\d+)?[),]?$/.test(clean)) continue
    // Unknown token
    errors.push({ line: 1, column: 0, message: `未知标识符: "${clean}"`, severity: 'error' })
  }

  return errors
}

// ── Module-level state for Monaco language registration ─────────────────────
let _langRegistered = false
// Module-level completions reference, updated when API data arrives
let _latestCompletions = CONDITION_DSL_COMPLETIONS

// ── Component ──────────────────────────────────────────────────────────────

export function RuleConditionEditor({ label, value, onChange, assetId }: RuleConditionEditorProps) {
  const [isVisual, setIsVisual] = useState(false)
  const [showTemplates, setShowTemplates] = useState(false)
  const [showHelp, setShowHelp] = useState(false)
  const [diagnostics, setDiagnostics] = useState<DslDiagnostic[]>([])
  const editorRef = useRef<editorTypes.IStandaloneCodeEditor | null>(null)
  const monacoRef = useRef<typeof import('monaco-editor') | null>(null)

  // Fetch indicators for dynamic autocomplete
  const { data: indData } = useQuery({
    queryKey: ['indicators'],
    queryFn: () => indicatorsApi.list(),
    staleTime: 300_000,
  })

  // Update module-level completions when API data changes
  useEffect(() => {
    if (indData?.indicators) {
      _latestCompletions = buildDynamicCompletions(indData.indicators)
    }
  }, [indData])

  // Validate on every change
  useEffect(() => {
    setDiagnostics(validateDsl(value))
  }, [value])

  // Register DSL language with Monaco once
  const handleEditorMount = useCallback(
    (editor: editorTypes.IStandaloneCodeEditor, monaco: typeof import('monaco-editor')) => {
      editorRef.current = editor
      monacoRef.current = monaco

      if (!_langRegistered) {
        // Register language
        monaco.languages.register({ id: CONDITION_DSL_LANG_ID })
        monaco.languages.setMonarchTokensProvider(CONDITION_DSL_LANG_ID, CONDITION_DSL_LANG)

        // Register theme
        monaco.editor.defineTheme('condition-dsl-theme', CONDITION_DSL_THEME)

        // Register completion provider
        monaco.languages.registerCompletionItemProvider(CONDITION_DSL_LANG_ID, {
          provideCompletionItems: (model, position) => {
            const word = model.getWordUntilPosition(position)
            const range = {
              startLineNumber: position.lineNumber,
              endLineNumber: position.lineNumber,
              startColumn: word.startColumn,
              endColumn: word.endColumn,
            }
            return {
              suggestions: _latestCompletions.map(item => ({
                ...item,
                range,
              })),
            }
          },
        })

        _langRegistered = true
      }

      // Apply the theme
      monaco.editor.setTheme('condition-dsl-theme')
    },
    [],
  )

  // Mark DSL diagnostics as Monaco markers
  useEffect(() => {
    const monaco = monacoRef.current
    const editor = editorRef.current
    if (!monaco || !editor) return

    const model = editor.getModel()
    if (!model) return

    const markers: editorTypes.IMarkerData[] = diagnostics.map(d => ({
      severity: monaco.MarkerSeverity.Error,
      message: d.message,
      startLineNumber: d.line,
      startColumn: d.column || 1,
      endLineNumber: d.line,
      endColumn: d.column ? d.column + 1 : model.getLineMaxColumn(d.line),
    }))

    monaco.editor.setModelMarkers(model, 'condition-dsl', markers)
  }, [diagnostics])

  // Apply template
  const handleTemplateSelect = useCallback(
    (tpl: StrategyTemplate) => {
      onChange(tpl.entry[0])
      setShowTemplates(false)
    },
    [onChange],
  )

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900 text-sm">{label}</h3>
        <div className="flex items-center gap-2">
          {diagnostics.length === 0 && value.trim() && (
            <span className="text-[11px] text-green-600 bg-green-50 px-2 py-0.5 rounded">语法正确</span>
          )}
          {diagnostics.length > 0 && (
            <span className="text-[11px] text-red-600 bg-red-50 px-2 py-0.5 rounded">
              {diagnostics.length} 个错误
            </span>
          )}
          <button
            className={`text-xs px-2 py-1 rounded transition-colors ${showTemplates ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            onClick={() => setShowTemplates(!showTemplates)}
          >
            模板
          </button>
          <button
            className={`text-xs px-2 py-1 rounded transition-colors ${showHelp ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            onClick={() => setShowHelp(!showHelp)}
          >
            帮助
          </button>
          <button
            className={`text-xs px-2 py-1 rounded transition-colors ${isVisual ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            onClick={() => setIsVisual(!isVisual)}
          >
            {isVisual ? '代码' : '可视化'}
          </button>
        </div>
      </div>

      {/* Templates panel */}
      {showTemplates && (
        <StrategyTemplates onSelect={handleTemplateSelect} />
      )}

      {/* Editor area with optional help panel */}
      <div className="flex gap-2">
        <div className="flex-1 min-w-0">
          {/* Monaco editor (code mode) */}
          {!isVisual && (
            <div className="space-y-2">
              <Suspense
                fallback={
                  <div className="h-32 bg-gray-50 animate-pulse rounded flex items-center justify-center text-xs text-gray-400">
                    Loading editor...
                  </div>
                }
              >
                <MonacoEditor
                  height="120px"
                  language={CONDITION_DSL_LANG_ID}
                  value={value}
                  onChange={v => onChange(v ?? '')}
                  onMount={handleEditorMount}
                  options={{
                    minimap: { enabled: false },
                    fontSize: 13,
                    scrollBeyondLastLine: false,
                    lineNumbers: 'off',
                    folding: false,
                    glyphMargin: false,
                    lineDecorationsWidth: 4,
                    overviewRulerLanes: 0,
                    scrollbar: { vertical: 'hidden' },
                    wordWrap: 'on',
                    suggest: { showKeywords: true },
                  }}
                />
              </Suspense>

              {/* Inline error messages */}
              {diagnostics.length > 0 && (
                <div className="space-y-1">
                  {diagnostics.map((d, i) => (
                    <div key={i} className="text-xs text-red-600 flex items-center gap-1">
                      <svg className="w-3 h-3 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                      </svg>
                      {d.message}
                    </div>
                  ))}
                </div>
              )}

              {/* Hint */}
              <div className="text-[11px] text-gray-400">
                支持: sma(20), rsi(14), close, AND/OR, crosses_above, &gt;/&lt;/==
              </div>
            </div>
          )}

          {/* Visual editor mode */}
          {isVisual && (
            <ConditionEditor
              label=""
              value={value}
              onChange={onChange}
              assetId={assetId}
            />
          )}
        </div>

        {/* Help panel */}
        {showHelp && (
          <div className="w-64 border-l overflow-y-auto max-h-[400px]">
            <IndicatorReferencePanel />
          </div>
        )}
      </div>
    </div>
  )
}

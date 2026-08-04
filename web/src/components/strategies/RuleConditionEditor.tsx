/**
 * RuleConditionEditor — Monaco editor with DSL syntax highlighting for strategy rules.
 *
 * Combines a Monaco editor (with syntax highlighting, auto-completion, and validation)
 * with a toggle to switch to the visual ConditionEditor. Loads templates from
 * StrategyTemplates for quick starts.
 */
import { useState, useEffect, useCallback, useRef, lazy, Suspense } from 'react'
import type { editor as editorTypes } from 'monaco-editor'
import { useTranslation } from 'react-i18next'
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

// Built-in function/keyword names that cannot be used as let-binding names
const BUILTIN_NAMES = new Set([
  'AND', 'OR', 'NOT', 'for', 'within', 'after', 'bars', 'let',
  'crosses_above', 'crosses_below',
  'rsi', 'sma', 'ema', 'wma', 'macd', 'macd_signal', 'macd_hist',
  'bb_upper', 'bb_lower', 'bb_mid', 'atr', 'kdj_k', 'kdj_d', 'kdj_j',
  'adx', 'cci', 'stoch_k', 'stoch_d', 'williams_r', 'roc', 'momentum',
  'obv', 'mfi', 'volume_sma', 'volume_ratio',
  'close', 'open', 'high', 'low', 'volume',
])

function validateDsl(dsl: string): DslDiagnostic[] {
  if (!dsl.trim()) return []

  const errors: DslDiagnostic[] = []
  const lines = dsl.split('\n')
  const definedVars = new Set<string>()

  for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
    const line = lines[lineIdx]
    const lineNum = lineIdx + 1
    const trimmed = line.trim()

    // Skip empty lines
    if (!trimmed) continue

    // Let binding line
    if (trimmed.startsWith('let ')) {
      const eqIdx = trimmed.indexOf('=')
      if (eqIdx === -1) {
        errors.push({ message: 'let binding must have format: let name = expression', line: lineNum, column: 1 })
        continue
      }
      const varName = trimmed.slice(4, eqIdx).trim()
      if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(varName)) {
        errors.push({ message: `Invalid variable name "${varName}"`, line: lineNum, column: 5 })
      } else if (BUILTIN_NAMES.has(varName)) {
        errors.push({ message: `"${varName}" conflicts with a built-in name`, line: lineNum, column: 5 })
      } else {
        definedVars.add(varName)
      }
      const expr = trimmed.slice(eqIdx + 1).trim()
      if (!expr) {
        errors.push({ message: 'let binding expression is empty', line: lineNum, column: eqIdx + 2 })
      }
      continue
    }

    // Condition line — validate parentheses and operators
    let depth = 0
    for (let i = 0; i < line.length; i++) {
      if (line[i] === '(') depth++
      if (line[i] === ')') depth--
      if (depth < 0) {
        errors.push({ message: 'Unmatched closing parenthesis', line: lineNum, column: i + 1 })
        break
      }
    }
    if (depth > 0) {
      errors.push({ message: 'Unmatched opening parenthesis', line: lineNum, column: line.length })
    }

    // Check that comparisons have two sides
    const tokens = trimmed.split(/\s+/)
    for (let i = 0; i < tokens.length; i++) {
      if (/^(>=|<=|!=|==|>|<)$/.test(tokens[i])) {
        if (i === 0 || i === tokens.length - 1) {
          errors.push({ message: `Operator "${tokens[i]}" needs operands on both sides`, line: lineNum, column: 0 })
        }
      }
      if (/^crosses_above|crosses_below$/.test(tokens[i])) {
        if (i === 0 || i === tokens.length - 1) {
          errors.push({ message: `"${tokens[i]}" needs operands on both sides`, line: lineNum, column: 0 })
        }
      }
    }

  }

  // Note: Unknown identifier validation is intentionally omitted here.
  // The Monaco autocomplete provides dynamic indicator names from the API,
  // so a static keyword list would produce false positives for valid indicators.

  return errors
}

// ── Module-level state for Monaco language registration ─────────────────────
let _langRegistered = false
// Module-level completions reference, updated when API data arrives
let _latestCompletions = CONDITION_DSL_COMPLETIONS

// ── Component ──────────────────────────────────────────────────────────────

export function RuleConditionEditor({ label, value, onChange, assetId }: RuleConditionEditorProps) {
  const { t } = useTranslation()
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
            <span className="text-[11px] text-green-600 bg-green-50 px-2 py-0.5 rounded">{t('component.strategies.rule_condition_editor.syntax_ok')}</span>
          )}
          {diagnostics.length > 0 && (
            <span className="text-[11px] text-red-600 bg-red-50 px-2 py-0.5 rounded">
              {t('component.strategies.rule_condition_editor.error_count', { count: diagnostics.length })}
            </span>
          )}
          <button
            className={`text-xs px-2 py-1 rounded transition-colors ${showTemplates ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            onClick={() => setShowTemplates(!showTemplates)}
          >
            {t('component.strategies.rule_condition_editor.templates')}
          </button>
          <button
            className={`text-xs px-2 py-1 rounded transition-colors ${showHelp ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            onClick={() => setShowHelp(!showHelp)}
          >
            {t('component.strategies.rule_condition_editor.help')}
          </button>
          <button
            className={`text-xs px-2 py-1 rounded transition-colors ${isVisual ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            onClick={() => setIsVisual(!isVisual)}
          >
            {isVisual ? t('component.strategies.rule_condition_editor.mode_code') : t('component.strategies.rule_condition_editor.mode_visual')}
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
                    {t('component.strategies.rule_condition_editor.loading_editor')}
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
                {t('component.strategies.rule_condition_editor.hint')}
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

/**
 * Monarch language definition for the Condition DSL used in strategy rules.
 *
 * Provides syntax highlighting, bracket colorization, and auto-completion
 * for the Monaco editor.
 */
import type { languages, editor } from 'monaco-editor'

// ── Language definition ────────────────────────────────────────────────────

export const CONDITION_DSL_LANG_ID = 'condition-dsl'

export const CONDITION_DSL_LANG: languages.IMonarchLanguage = {
  defaultToken: '',
  keywords: ['AND', 'OR', 'NOT', 'for', 'within', 'after', 'bars'],
  builtinFunctions: [
    'crosses_above',
    'crosses_below',
  ],
  indicators: [
    'rsi', 'sma', 'ema', 'wma', 'macd', 'macd_signal', 'macd_hist',
    'bb_upper', 'bb_lower', 'bb_mid', 'atr', 'kdj_k', 'kdj_d', 'kdj_j',
    'adx', 'cci', 'stoch_k', 'stoch_d', 'williams_r', 'roc', 'momentum',
    'obv', 'mfi', 'volume_sma', 'volume_ratio',
    'close', 'open', 'high', 'low', 'volume',
  ],
  operators: ['>', '<', '>=', '<=', '==', '!='],

  tokenizer: {
    root: [
      // Comments
      [/\/\/.*$/, 'comment'],

      // Keywords (uppercase words)
      [/\b(?:AND|OR|NOT|for|within|after|bars)\b/, 'keyword'],

      // Built-in functions
      [/\b(?:crosses_above|crosses_below)\b/, 'type.identifier'],

      // Known indicator names — color differently when followed by '('
      [/\b(?:rsi|sma|ema|wma|macd|macd_signal|macd_hist|bb_upper|bb_lower|bb_mid|atr|kdj_k|kdj_d|kdj_j|adx|cci|stoch_k|stoch_d|williams_r|roc|momentum|obv|mfi|volume_sma|volume_ratio)(?=\s*\()/, 'tag'],

      // Price field names (standalone, not followed by '(')
      [/\b(?:close|open|high|low|volume)\b/, 'variable'],

      // Any other identifier that looks like a function call
      [/[a-z_][a-z0-9_]*(?=\s*\()/, 'tag'],

      // Any other lowercase identifier
      [/[a-z_][a-z0-9_]*/, 'variable'],

      // Numbers (integers and floats)
      [/\d+(\.\d+)?/, 'number'],

      // Operators
      [/(?:>=|<=|!=|==|>|<)/, 'operator'],

      // Parentheses
      [/[()]/, '@brackets'],

      // Comma
      [/,/, 'delimiter'],

      // Skip whitespace
      [/\s+/, 'white'],
    ],
  },
}

// ── Auto-completion items ──────────────────────────────────────────────────

const InsertTextRule = {
  None: 0 as const,
  KeepWhitespace: 1 as const,
  InsertAsSnippet: 4 as const,
}

const CompletionItemKind = {
  Function: 3 as const,
  Variable: 6 as const,
  Keyword: 14 as const,
  Operator: 11 as const,
}

type CompletionBase = Omit<languages.CompletionItem, 'range'>

export const CONDITION_DSL_COMPLETIONS: CompletionBase[] = [
  // ── Indicators (function-call style) ──
  { label: 'rsi', kind: CompletionItemKind.Function, insertText: 'rsi(${1:14})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'RSI(period=14)', documentation: 'Relative Strength Index' },
  { label: 'sma', kind: CompletionItemKind.Function, insertText: 'sma(${1:20})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'SMA(period=20)', documentation: 'Simple Moving Average' },
  { label: 'ema', kind: CompletionItemKind.Function, insertText: 'ema(${1:20})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'EMA(period=20)', documentation: 'Exponential Moving Average' },
  { label: 'wma', kind: CompletionItemKind.Function, insertText: 'wma(${1:20})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'WMA(period=20)', documentation: 'Weighted Moving Average' },
  { label: 'macd', kind: CompletionItemKind.Function, insertText: 'macd(${1:12}, ${2:26}, ${3:9})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'MACD(fast, slow, signal)', documentation: 'Moving Average Convergence Divergence' },
  { label: 'macd_signal', kind: CompletionItemKind.Function, insertText: 'macd_signal(${1:12}, ${2:26}, ${3:9})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'MACD Signal Line', documentation: 'MACD Signal line' },
  { label: 'macd_hist', kind: CompletionItemKind.Function, insertText: 'macd_hist(${1:12}, ${2:26}, ${3:9})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'MACD Histogram', documentation: 'MACD Histogram (MACD - Signal)' },
  { label: 'bb_upper', kind: CompletionItemKind.Function, insertText: 'bb_upper(${1:20}, ${2:2})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'BB Upper(period, std_dev)', documentation: 'Bollinger Band Upper' },
  { label: 'bb_lower', kind: CompletionItemKind.Function, insertText: 'bb_lower(${1:20}, ${2:2})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'BB Lower(period, std_dev)', documentation: 'Bollinger Band Lower' },
  { label: 'bb_mid', kind: CompletionItemKind.Function, insertText: 'bb_mid(${1:20})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'BB Mid(period)', documentation: 'Bollinger Band Middle' },
  { label: 'atr', kind: CompletionItemKind.Function, insertText: 'atr(${1:14})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'ATR(period=14)', documentation: 'Average True Range' },
  { label: 'kdj_k', kind: CompletionItemKind.Function, insertText: 'kdj_k(${1:14}, ${2:3})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'KDJ K(k_period, d_period)', documentation: 'KDJ K line' },
  { label: 'kdj_d', kind: CompletionItemKind.Function, insertText: 'kdj_d(${1:14}, ${2:3})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'KDJ D(k_period, d_period)', documentation: 'KDJ D line' },
  { label: 'kdj_j', kind: CompletionItemKind.Function, insertText: 'kdj_j(${1:14}, ${2:3})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'KDJ J(k_period, d_period)', documentation: 'KDJ J line' },
  { label: 'adx', kind: CompletionItemKind.Function, insertText: 'adx(${1:14})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'ADX(period=14)', documentation: 'Average Directional Index' },
  { label: 'cci', kind: CompletionItemKind.Function, insertText: 'cci(${1:20})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'CCI(period=20)', documentation: 'Commodity Channel Index' },
  { label: 'stoch_k', kind: CompletionItemKind.Function, insertText: 'stoch_k(${1:14}, ${2:3})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'Stoch K(k_period, d_period)', documentation: 'Stochastic K' },
  { label: 'stoch_d', kind: CompletionItemKind.Function, insertText: 'stoch_d(${1:14}, ${2:3})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'Stoch D(k_period, d_period)', documentation: 'Stochastic D' },
  { label: 'williams_r', kind: CompletionItemKind.Function, insertText: 'williams_r(${1:14})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'Williams %R(period=14)', documentation: 'Williams %R' },
  { label: 'roc', kind: CompletionItemKind.Function, insertText: 'roc(${1:12})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'ROC(period=12)', documentation: 'Rate of Change' },
  { label: 'momentum', kind: CompletionItemKind.Function, insertText: 'momentum(${1:10})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'Momentum(period=10)', documentation: 'Price Momentum' },
  { label: 'obv', kind: CompletionItemKind.Function, insertText: 'obv()', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'OBV()', documentation: 'On-Balance Volume' },
  { label: 'mfi', kind: CompletionItemKind.Function, insertText: 'mfi(${1:14})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'MFI(period=14)', documentation: 'Money Flow Index' },
  { label: 'volume_sma', kind: CompletionItemKind.Function, insertText: 'volume_sma(${1:20})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'Volume SMA(period=20)', documentation: 'Volume Simple Moving Average' },
  { label: 'volume_ratio', kind: CompletionItemKind.Function, insertText: 'volume_ratio(${1:5})', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'Volume Ratio(period=5)', documentation: 'Current volume / average volume' },

  // ── Price fields ──
  { label: 'close', kind: CompletionItemKind.Variable, insertText: 'close', detail: 'Close price', documentation: 'Closing price of the bar' },
  { label: 'open', kind: CompletionItemKind.Variable, insertText: 'open', detail: 'Open price', documentation: 'Opening price of the bar' },
  { label: 'high', kind: CompletionItemKind.Variable, insertText: 'high', detail: 'High price', documentation: 'Highest price of the bar' },
  { label: 'low', kind: CompletionItemKind.Variable, insertText: 'low', detail: 'Low price', documentation: 'Lowest price of the bar' },
  { label: 'volume', kind: CompletionItemKind.Variable, insertText: 'volume', detail: 'Volume', documentation: 'Trading volume of the bar' },

  // ── Keywords ──
  { label: 'AND', kind: CompletionItemKind.Keyword, insertText: 'AND', detail: 'Logical AND', documentation: 'Both conditions must be true' },
  { label: 'OR', kind: CompletionItemKind.Keyword, insertText: 'OR', detail: 'Logical OR', documentation: 'Either condition must be true' },
  { label: 'NOT', kind: CompletionItemKind.Keyword, insertText: 'NOT', detail: 'Logical NOT', documentation: 'Negate the condition' },
  { label: 'crosses_above', kind: CompletionItemKind.Keyword, insertText: 'crosses_above', detail: 'Crosses above', documentation: 'True when first value crosses above second' },
  { label: 'crosses_below', kind: CompletionItemKind.Keyword, insertText: 'crosses_below', detail: 'Crosses below', documentation: 'True when first value crosses below second' },
  { label: 'for', kind: CompletionItemKind.Keyword, insertText: 'for ${1:N} bars', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'for N bars', documentation: 'Condition holds for N consecutive bars' },
  { label: 'within', kind: CompletionItemKind.Keyword, insertText: 'within ${1:N} bars', insertTextRules: InsertTextRule.InsertAsSnippet, detail: 'within N bars', documentation: 'Condition was true within the last N bars' },
]

// ── Dynamic completions builder ────────────────────────────────────────────

/**
 * Generate completion items from API indicator data.
 * Falls back to static CONDITION_DSL_COMPLETIONS if no data.
 */
export function buildDynamicCompletions(
  indicators: Array<{
    name: string
    description?: string
    params?: Array<{ name: string; default?: number }>
  }>,
): CompletionBase[] {
  if (!indicators.length) return CONDITION_DSL_COMPLETIONS

  const indicatorCompletions: CompletionBase[] = indicators.map(ind => {
    const params = ind.params || []
    let insertText: string
    if (params.length === 0) {
      insertText = `${ind.name}()`
    } else {
      const snippetParts = params.map((p, i) => {
        const defaultVal = p.default ?? ''
        return `\${${i + 1}:${defaultVal}}`
      })
      insertText = `${ind.name}(${snippetParts.join(', ')})`
    }

    const detailParts = params.map(p => p.name).join(', ')
    const detail =
      params.length > 0
        ? `${ind.name}(${detailParts})`
        : `${ind.name}()`

    return {
      label: ind.name,
      kind: CompletionItemKind.Function,
      insertText,
      insertTextRules: InsertTextRule.InsertAsSnippet,
      detail,
      documentation: ind.description || ind.name,
    }
  })

  // Keep non-indicator completions (price fields, keywords, operators) from static list
  const nonIndicatorCompletions = CONDITION_DSL_COMPLETIONS.filter(
    c => c.kind !== CompletionItemKind.Function,
  )

  return [...indicatorCompletions, ...nonIndicatorCompletions]
}

// ── Theme rules ───────────────────────────────────────────────────────────

export const CONDITION_DSL_THEME: editor.IStandaloneThemeData = {
  base: 'vs',
  inherit: true,
  rules: [
    { token: 'comment', foreground: '6a9955', fontStyle: 'italic' },
    { token: 'keyword', foreground: '0000ff', fontStyle: 'bold' },
    { token: 'type.identifier', foreground: '795E26' },   // crosses_above/below
    { token: 'tag', foreground: '267F99' },                 // indicator functions
    { token: 'variable', foreground: '0070C1' },            // price fields
    { token: 'number', foreground: '098658' },
    { token: 'operator', foreground: 'AF00DB' },
    { token: 'delimiter', foreground: '000000' },
    { token: 'brackets', foreground: '000000' },
  ],
  colors: {},
}

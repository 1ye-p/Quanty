import { useState, lazy, Suspense } from 'react'
import { useQuery } from '@tanstack/react-query'
import { dslApi, customFactorApi } from '@/lib/api'
import { extendedQueryKeys } from '@/lib/queryKeys'

const Editor = lazy(() => import('@monaco-editor/react'))

interface Props {
  onSave: (expression: string, name?: string) => void
  initialExpression?: string
}

export function FactorDSLEditor({ onSave, initialExpression = '' }: Props) {
  const [expr, setExpr] = useState(initialExpression)
  const [name, setName] = useState('')
  const [preview, setPreview] = useState<Record<string, unknown>[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showHelp, setShowHelp] = useState(false)

  const { data: dslMeta } = useQuery({
    queryKey: extendedQueryKeys.dsl.functions,
    queryFn: dslApi.functions,
    staleTime: 300_000,
  })

  async function handlePreview() {
    setError(null)
    setPreview(null)
    try {
      const result = await customFactorApi.preview({ expression: expr })
      if (result.valid) {
        setPreview(result.preview ?? [])
      } else {
        setError(result.error ?? '表达式无效')
      }
    } catch (e) {
      setError(String(e))
    }
  }

  function handleSave() {
    onSave(expr, name || undefined)
  }

  function fillExample(expression: string) {
    setExpr(expression)
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium text-gray-700">因子名称</label>
        <input
          className="input mt-1 max-w-xs"
          placeholder="my_momentum"
          value={name}
          onChange={e => setName(e.target.value)}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-3">
          <Suspense fallback={<div className="h-64 bg-gray-50 animate-pulse rounded" />}>
            <Editor
              height="240px"
              language="plaintext"
              value={expr}
              onChange={v => setExpr(v ?? '')}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                scrollBeyondLastLine: false,
                lineNumbers: 'off',
              }}
            />
          </Suspense>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 p-2 rounded">{error}</div>
          )}

          {preview && preview.length > 0 && (
            <div className="card p-0 overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-gray-50">
                  <tr>
                    {Object.keys(preview[0]).map(k => (
                      <th key={k} className="table-th">{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.map((row, i) => (
                    <tr key={i} className="table-row">
                      {Object.values(row).map((v, j) => (
                        <td key={j} className="table-td">{String(v ?? '—')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex gap-2">
            <button className="btn-secondary" onClick={handlePreview}>预览</button>
            <button className="btn-primary" onClick={handleSave}>保存</button>
          </div>
        </div>

        <div className="space-y-3">
          <button
            className="text-sm text-brand-600 hover:underline"
            onClick={() => setShowHelp(!showHelp)}
          >
            {showHelp ? '收起语法说明' : '语法说明 ▸'}
          </button>

          {showHelp && dslMeta && (
            <div className="card text-xs space-y-3 max-h-96 overflow-y-auto">
              <div>
                <h4 className="font-semibold text-gray-700 mb-1">可用列</h4>
                <div className="flex flex-wrap gap-1">
                  {dslMeta.columns.map(c => (
                    <span key={c} className="badge bg-blue-50 text-blue-700">{c}</span>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="font-semibold text-gray-700 mb-1">函数</h4>
                {dslMeta.functions.map(f => (
                  <div key={f.name} className="py-1 border-b border-gray-100 last:border-0">
                    <code className="text-brand-600 font-mono">{f.name}</code>
                    <span className="text-gray-500 ml-1">({f.minArgs === f.maxArgs ? f.minArgs : `${f.minArgs}-${f.maxArgs}`} args)</span>
                    <div className="text-gray-500">{f.description}</div>
                  </div>
                ))}
              </div>

              <div>
                <h4 className="font-semibold text-gray-700 mb-1">示例</h4>
                {dslMeta.examples.map(ex => (
                  <button
                    key={ex.name}
                    className="block w-full text-left py-1.5 px-2 rounded hover:bg-gray-50"
                    onClick={() => fillExample(ex.expression)}
                  >
                    <div className="text-gray-700">{ex.name}</div>
                    <code className="text-xs text-gray-500">{ex.expression}</code>
                  </button>
                ))}
              </div>

              <div>
                <h4 className="font-semibold text-gray-700 mb-1">运算符</h4>
                <div className="text-gray-600 space-y-0.5">
                  <div><code>+ - * / ^</code> 算术</div>
                  <div><code>&gt; &lt; &gt;= &lt;= == !=</code> 比较 (返回 0/1)</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import Editor from '@monaco-editor/react'
import { knowledgeApi } from '@/lib/api'
import { queryKeys } from '@/lib/queryKeys'

interface DocumentPreviewProps {
  docId: string | null
  fileName?: string
}

function getLanguageFromExtension(fileName: string): string {
  const ext = fileName.split('.').pop()?.toLowerCase() ?? ''
  const map: Record<string, string> = {
    py: 'python',
    pyw: 'python',
    js: 'javascript',
    ts: 'typescript',
    tsx: 'typescript',
    jsx: 'javascript',
    md: 'markdown',
    json: 'json',
    yaml: 'yaml',
    yml: 'yaml',
    csv: 'plaintext',
    txt: 'plaintext',
    sh: 'shell',
    bash: 'shell',
    sql: 'sql',
    html: 'html',
    css: 'css',
    r: 'r',
    rst: 'plaintext',
  }
  return map[ext] ?? 'plaintext'
}

export function DocumentPreview({ docId, fileName }: DocumentPreviewProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.knowledge.content(docId ?? ''),
    queryFn: () => knowledgeApi.getContent(docId!),
    enabled: !!docId,
  })

  if (!docId) {
    return (
      <div className="card h-full flex items-center justify-center text-gray-400 text-sm">
        选择文档以预览
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="card h-full flex items-center justify-center">
        <div className="animate-pulse space-y-3 w-full p-4">
          <div className="h-4 bg-gray-200 rounded w-3/4" />
          <div className="h-4 bg-gray-200 rounded w-1/2" />
          <div className="h-4 bg-gray-200 rounded w-2/3" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card h-full flex items-center justify-center text-red-500 text-sm">
        加载失败：{error instanceof Error ? error.message : String(error)}
      </div>
    )
  }

  if (!data?.content) {
    return (
      <div className="card h-full flex items-center justify-center text-gray-400 text-sm">
        无可预览内容
      </div>
    )
  }

  const language = data.language || (fileName ? getLanguageFromExtension(fileName) : 'plaintext')

  // Markdown: render as HTML
  if (language === 'markdown') {
    return (
      <div className="card h-full overflow-auto">
        <div
          className="prose prose-sm max-w-none p-4"
          dangerouslySetInnerHTML={{ __html: simpleMarkdownToHtml(data.content) }}
        />
      </div>
    )
  }

  // Code: Monaco Editor read-only
  return (
    <div className="card h-full p-0 overflow-hidden">
      <Editor
        height="100%"
        language={language}
        value={data.content}
        theme="vs-dark"
        options={{
          readOnly: true,
          domReadOnly: true,
          minimap: { enabled: false },
          fontSize: 13,
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          wordWrap: 'on',
          automaticLayout: true,
        }}
      />
    </div>
  )
}

/** Minimal markdown to HTML converter for preview. HTML-escapes input first to prevent XSS. */
function simpleMarkdownToHtml(md: string): string {
  // Escape HTML entities BEFORE applying markdown transformations
  const escaped = md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

  return escaped
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br/>')
}

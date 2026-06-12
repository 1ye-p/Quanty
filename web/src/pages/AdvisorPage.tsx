import { useState, useRef, useEffect } from 'react'
import { useAdvisorStream } from '@/hooks/useAdvisorStream'
import { advisorApi } from '@/lib/api'
import { toast } from 'sonner'
import {
  ResponsiveContainer,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend,
  BarChart, Bar,
  PieChart, Pie, Cell,
} from 'recharts'

// ── Chart rendering helpers ─────────────────────────────────────────────────

interface ChartPayload {
  chart_type: string
  title: string
  data: Record<string, unknown>[]
  config?: Record<string, unknown>
}

const PIE_COLORS = ['#3b82f6', '#f97316', '#ef4444', '#22c55e', '#a855f7', '#06b6d4', '#eab308', '#ec4899']

function MetricCards({ title, data }: { title: string; data: Record<string, unknown>[] }) {
  return (
    <div className="mb-3">
      <div className="text-xs font-bold uppercase tracking-wide text-gray-400 mb-2">{title}</div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {data.map((card, i) => (
          <div key={i} className="bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
            <div className="text-xs text-gray-500">{String(card.label ?? '')}</div>
            <div className="text-lg font-semibold text-gray-800">{String(card.value ?? '')}</div>
            {card.delta !== undefined && (
              <div className={`text-xs ${Number(card.delta) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {Number(card.delta) >= 0 ? '+' : ''}{String(card.delta)}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function LineChartWidget({ title, data, config }: { title: string; data: Record<string, unknown>[]; config?: Record<string, unknown> }) {
  const xKey = String(config?.x_key ?? 'date')
  const yKeys = (config?.y_keys as string[]) ?? Object.keys(data[0] ?? {}).filter(k => k !== xKey)
  if (!data.length || !yKeys.length) return null
  return (
    <div className="mb-3">
      <div className="text-xs font-bold uppercase tracking-wide text-gray-400 mb-2">{title}</div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey={xKey} tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <RechartsTooltip />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {yKeys.map((key, i) => (
            <Line key={key} type="monotone" dataKey={key} stroke={PIE_COLORS[i % PIE_COLORS.length]} dot={false} strokeWidth={1.5} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function BarChartWidget({ title, data, config }: { title: string; data: Record<string, unknown>[]; config?: Record<string, unknown> }) {
  const xKey = String(config?.x_key ?? 'category')
  const yKey = String(config?.y_key ?? 'value')
  if (!data.length) return null
  return (
    <div className="mb-3">
      <div className="text-xs font-bold uppercase tracking-wide text-gray-400 mb-2">{title}</div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey={xKey} tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <RechartsTooltip />
          <Bar dataKey={yKey} fill="#3b82f6" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function PieChartWidget({ title, data, config }: { title: string; data: Record<string, unknown>[]; config?: Record<string, unknown> }) {
  const nameKey = String(config?.name_key ?? 'name')
  const valueKey = String(config?.value_key ?? 'value')
  if (!data.length) return null
  return (
    <div className="mb-3">
      <div className="text-xs font-bold uppercase tracking-wide text-gray-400 mb-2">{title}</div>
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie data={data} dataKey={valueKey} nameKey={nameKey} cx="50%" cy="50%" outerRadius={80} label>
            {data.map((_, i) => (
              <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
            ))}
          </Pie>
          <RechartsTooltip />
          <Legend wrapperStyle={{ fontSize: 11 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

function ChartRenderer({ payload }: { payload: ChartPayload }) {
  switch (payload.chart_type) {
    case 'metric_cards':
      return <MetricCards title={payload.title} data={payload.data} />
    case 'line':
      return <LineChartWidget title={payload.title} data={payload.data} config={payload.config} />
    case 'bar':
      return <BarChartWidget title={payload.title} data={payload.data} config={payload.config} />
    case 'pie':
      return <PieChartWidget title={payload.title} data={payload.data} config={payload.config} />
    default:
      return null
  }
}

/** Parse [CHART:type:json] markers from text and render charts inline. */
function RichContent({ content }: { content: string }) {
  const parts: { type: 'text' | 'chart'; value: string; payload?: ChartPayload }[] = []
  const regex = /\[CHART:(\w+):([\s\S]*?)\]/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', value: content.slice(lastIndex, match.index) })
    }
    try {
      const payload = JSON.parse(match[2]) as ChartPayload
      parts.push({ type: 'chart', value: match[0], payload })
    } catch {
      parts.push({ type: 'text', value: match[0] })
    }
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < content.length) {
    parts.push({ type: 'text', value: content.slice(lastIndex) })
  }

  return (
    <>
      {parts.map((part, i) =>
        part.type === 'chart' && part.payload ? (
          <ChartRenderer key={i} payload={part.payload} />
        ) : (
          <span key={i}>{part.value}</span>
        )
      )}
    </>
  )
}

// ── Session sidebar ─────────────────────────────────────────────────────────

interface SessionEntry {
  id: string
  preview: string        // first 60 chars of user message
  createdAt: string
  turns: number
}

function SessionSidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
}: {
  sessions: SessionEntry[]
  activeId: string | undefined
  onSelect: (id: string) => void
  onNew: () => void
}) {
  return (
    <aside className="w-52 flex-shrink-0 flex flex-col border-r border-gray-200 bg-white">
      <div className="px-3 py-3 border-b border-gray-100 flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">历史会话</span>
        <button
          onClick={onNew}
          className="text-xs text-brand-600 hover:text-brand-700 font-medium"
          title="新建会话"
        >
          + 新建
        </button>
      </div>
      <div className="flex-1 overflow-y-auto py-1">
        {sessions.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-4 px-2">暂无历史会话</p>
        )}
        {sessions.map(s => (
          <button
            key={s.id}
            onClick={() => onSelect(s.id)}
            className={`w-full text-left px-3 py-2.5 hover:bg-gray-50 transition-colors border-l-2 ${
              s.id === activeId ? 'border-brand-500 bg-blue-50' : 'border-transparent'
            }`}
          >
            <div className="text-xs font-medium text-gray-800 truncate">{s.preview}</div>
            <div className="text-xs text-gray-400 mt-0.5">{s.turns} 轮 · {s.createdAt}</div>
          </button>
        ))}
      </div>
    </aside>
  )
}

interface AgentResult { agent: string; content: string; artifacts: string[] }

const AGENT_CONFIG: Record<string, { border: string; color: string }> = {
  research: { border: 'border-blue-400',   color: 'text-blue-700' },
  risk:     { border: 'border-orange-400', color: 'text-orange-700' },
  debate:   { border: 'border-red-400',    color: 'text-red-700' },
}

function AgentCard({ role, content, isActive }: { role: string; content?: string; isActive: boolean }) {
  const cfg = AGENT_CONFIG[role] ?? { border: 'border-gray-300', color: 'text-gray-600' }
  const labels: Record<string, string> = { research: '📊 Research', risk: '⚠️ Risk', debate: '🔴 Debate' }
  return (
    <div className={`agent-card ${cfg.border}`}>
      <div className={`text-xs font-bold uppercase tracking-wide mb-2 ${cfg.color}`}>
        {labels[role] ?? role}
      </div>
      {isActive && !content && (
        <div className="flex items-center gap-2 text-gray-400 text-sm">
          <span className="animate-spin inline-block">⟳</span> 分析中…
        </div>
      )}
      {content && (
        <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
          <RichContent content={content} />
        </div>
      )}
      {!content && !isActive && <p className="text-sm text-gray-300">等待中</p>}
    </div>
  )
}

const MAX_SESSIONS = 20

export function AdvisorPage() {
  const [sessions, setSessions] = useState<SessionEntry[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | undefined>()
  const [usePanel, setUsePanel] = useState(true)
  const [input, setInput] = useState('')
  const pendingMessageRef = useRef<string>('')

  const { state: stream, start: startStream, reset: resetStream } = useAdvisorStream()

  const [reportSubject, setReportSubject] = useState('')
  const [generatingReport, setGeneratingReport] = useState(false)

  const handleGenerateReport = async () => {
    if (!reportSubject.trim()) return
    setGeneratingReport(true)
    try {
      const result = await advisorApi.report(reportSubject, activeSessionId)
      const blob = new Blob([result.report], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `cquant-report-${new Date().toISOString().slice(0, 10)}.md`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('报告已生成并下载')
    } catch (e: unknown) {
      toast.error(`报告生成失败: ${(e as Error).message}`)
    } finally {
      setGeneratingReport(false)
    }
  }

  const [chatHistory, setChatHistory] = useState<{ role: string; content: string }[]>([])
  const [chatLoading, setChatLoading] = useState(false)
  const chatBottomRef = useRef<HTMLDivElement>(null)

  // Register session when SSE stream delivers a session_id
  useEffect(() => {
    if (stream.sessionId && stream.status !== 'idle' && pendingMessageRef.current) {
      registerSession(stream.sessionId, pendingMessageRef.current, 1)
    }
  }, [stream.sessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  function createNewSession() {
    resetStream()
    setChatHistory([])
    setActiveSessionId(undefined)
    pendingMessageRef.current = ''
  }

  function selectSession(id: string) {
    resetStream()
    setChatHistory([])
    setActiveSessionId(id)
  }

  function registerSession(sessionId: string, userMessage: string, turnCount: number) {
    const entry: SessionEntry = {
      id: sessionId,
      preview: userMessage.slice(0, 55) + (userMessage.length > 55 ? '…' : ''),
      createdAt: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      turns: turnCount,
    }
    setSessions(prev => {
      const idx = prev.findIndex(s => s.id === sessionId)
      if (idx >= 0) {
        const next = [...prev]
        next[idx] = { ...next[idx], turns: turnCount }
        return next
      }
      // Cap at MAX_SESSIONS, newest first
      return [entry, ...prev].slice(0, MAX_SESSIONS)
    })
    setActiveSessionId(sessionId)
  }

  async function handleSend() {
    const text = input.trim()
    if (!text) return
    setInput('')

    if (usePanel) {
      resetStream()
      pendingMessageRef.current = text
      startStream(text, activeSessionId)
    } else {
      setChatHistory(h => [...h, { role: 'user', content: text }])
      setChatLoading(true)
      try {
        const resp = await advisorApi.chat(text, activeSessionId)
        registerSession(resp.session_id, text, chatHistory.length / 2 + 1)
        setChatHistory(h => [...h, { role: 'assistant', content: resp.response }])
        setTimeout(() => chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
      } catch (e) {
        setChatHistory(h => [...h, { role: 'assistant', content: `错误: ${e}` }])
      } finally {
        setChatLoading(false)
      }
    }
  }

  return (
    <div className="flex h-[calc(100vh-5rem)] -m-8">
      {/* Session sidebar */}
      <SessionSidebar
        sessions={sessions}
        activeId={activeSessionId}
        onSelect={selectSession}
        onNew={createNewSession}
      />

      {/* Main chat area */}
      <div className="flex-1 flex flex-col p-6 overflow-hidden">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">AI 分析助手</h1>
            <p className="text-xs text-gray-400">仅限离线研究 · 不执行真实交易 · 多智能体 RAG</p>
          </div>
          <div className="flex items-center gap-2">
            {activeSessionId && (
              <span className="text-xs text-gray-400 font-mono">
                Session: {activeSessionId.slice(0, 8)}…
              </span>
            )}
            <div className="flex items-center gap-1.5">
              <input
                type="text"
                value={reportSubject}
                onChange={e => setReportSubject(e.target.value)}
                placeholder="报告主题"
                className="input text-xs w-40"
                onKeyDown={e => { if (e.key === 'Enter') void handleGenerateReport() }}
              />
              <button
                onClick={() => void handleGenerateReport()}
                disabled={!reportSubject.trim() || generatingReport}
                className="text-xs text-green-600 hover:text-green-700 font-medium px-2 py-1 rounded border border-green-300 hover:bg-green-50 disabled:opacity-40"
                title="生成投研报告"
              >
                {generatingReport ? '生成中…' : '📄 报告'}
              </button>
            </div>
            <button
              onClick={() => setUsePanel(!usePanel)}
              className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                usePanel
                  ? 'bg-brand-600 text-white border-brand-600'
                  : 'bg-white text-gray-600 border-gray-200'
              }`}
            >
              {usePanel ? '多角色面板' : '单次对话'}
            </button>
          </div>
        </div>

        {/* Panel mode */}
        {usePanel && (
          <div className="flex-1 overflow-y-auto space-y-4 pb-4">
            {stream.ragPreview && (
              <div className="text-xs text-gray-400 bg-gray-50 rounded-lg px-3 py-2">
                📚 RAG 上下文：{stream.ragPreview}
              </div>
            )}

            {(stream.status !== 'idle' || Object.keys(stream.agents).length > 0) && (
              <>
                <div className="flex gap-3">
                  {(['research', 'risk', 'debate'] as const).map(role => (
                    <AgentCard
                      key={role}
                      role={role}
                      content={(stream.agents[role] as AgentResult | undefined)?.content}
                      isActive={stream.activeAgent === role}
                    />
                  ))}
                </div>

                {(stream.report || stream.status === 'done') && (
                  <div className="card border-l-4 border-gray-200">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-bold uppercase tracking-wide text-gray-400">📄 Report Writer</span>
                      {stream.report && (
                        <button
                          className="text-xs text-blue-500 hover:underline"
                          onClick={() => navigator.clipboard.writeText(stream.report)}
                        >
                          复制报告
                        </button>
                      )}
                    </div>
                    <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                      {stream.report
                        ? <RichContent content={stream.report} />
                        : <span className="text-gray-300">生成中…</span>
                      }
                    </div>
                  </div>
                )}

                {stream.status === 'error' && (
                  <div className="bg-red-50 text-red-700 rounded-lg px-4 py-3 text-sm">
                    {stream.error}
                  </div>
                )}
              </>
            )}

            {stream.status === 'idle' && Object.keys(stream.agents).length === 0 && (
              <div className="text-center text-gray-400 mt-16">
                <div className="text-4xl mb-3">🤖</div>
                <div className="text-sm">
                  {activeSessionId ? '继续历史会话——输入新问题' : '输入问题后，多个 Agent 并行分析'}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Single-turn chat mode */}
        {!usePanel && (
          <div className="flex-1 overflow-y-auto space-y-3 pb-4">
            {chatHistory.length === 0 && (
              <div className="text-center text-gray-400 mt-16">
                <div className="text-4xl mb-3">💬</div>
                <div className="text-sm">单次对话模式，直接问答</div>
              </div>
            )}
            {chatHistory.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm whitespace-pre-wrap leading-relaxed shadow-sm ${
                  m.role === 'user'
                    ? 'bg-brand-600 text-white rounded-br-sm'
                    : 'bg-white text-gray-800 border border-gray-100 rounded-bl-sm'
                }`}>
                  {m.role === 'assistant' ? <RichContent content={m.content} /> : m.content}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="flex justify-start">
                <div className="bg-white border border-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 text-gray-400 text-sm shadow-sm">
                  分析中…
                </div>
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>
        )}

        {/* Input */}
        <div className="flex gap-2 pt-4 border-t border-gray-200">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void handleSend()
              }
            }}
            rows={3}
            placeholder="提问… (Enter 发送, Shift+Enter 换行)"
            className="input flex-1 resize-none"
            disabled={stream.status === 'streaming' || chatLoading}
          />
          <button
            onClick={() => void handleSend()}
            disabled={!input.trim() || stream.status === 'streaming' || chatLoading}
            className="btn-primary self-end"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  )
}

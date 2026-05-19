import { useState, useRef, useCallback, useEffect } from 'react'
import { advisorExtApi } from '@/lib/api'

export interface AgentResult {
  agent: 'research' | 'risk' | 'debate' | string
  content: string
  artifacts: string[]
}

export interface StreamState {
  status: 'idle' | 'connecting' | 'streaming' | 'done' | 'error'
  sessionId: string
  agents: Record<string, AgentResult>
  activeAgent: string | null
  report: string
  error: string
  ragPreview: string
}

const INITIAL: StreamState = {
  status: 'idle', sessionId: '', agents: {},
  activeAgent: null, report: '', error: '', ragPreview: '',
}

export function useAdvisorStream() {
  const [state, setState] = useState<StreamState>(INITIAL)
  const esRef = useRef<EventSource | null>(null)

  // Close EventSource on unmount to prevent connection leaks
  useEffect(() => () => { esRef.current?.close() }, [])

  const start = useCallback((message: string, sessionId?: string) => {
    esRef.current?.close()
    setState({ ...INITIAL, status: 'connecting' })

    const url = advisorExtApi.streamUrl(message, sessionId)
    const es = new EventSource(url)
    esRef.current = es

    es.addEventListener('session_started', (e) => {
      const d = JSON.parse((e as MessageEvent).data)
      setState(s => ({ ...s, status: 'streaming', sessionId: d.session_id }))
    })
    es.addEventListener('rag_done', (e) => {
      const d = JSON.parse((e as MessageEvent).data)
      setState(s => ({ ...s, ragPreview: d.context_preview }))
    })
    es.addEventListener('agent_start', (e) => {
      const d = JSON.parse((e as MessageEvent).data)
      setState(s => ({ ...s, activeAgent: d.agent }))
    })
    es.addEventListener('agent_done', (e) => {
      const d = JSON.parse((e as MessageEvent).data)
      setState(s => ({
        ...s,
        activeAgent: null,
        agents: { ...s.agents, [d.agent]: { agent: d.agent, content: d.content, artifacts: d.artifacts ?? [] } },
      }))
    })
    es.addEventListener('final_report', (e) => {
      const d = JSON.parse((e as MessageEvent).data)
      setState(s => ({ ...s, report: d.content }))
    })
    es.addEventListener('done', () => {
      setState(s => ({ ...s, status: 'done', activeAgent: null }))
      es.close()
    })
    es.addEventListener('error', (e) => {
      const msg = e instanceof MessageEvent ? JSON.parse(e.data).message : 'Connection error'
      setState(s => ({ ...s, status: 'error', error: msg }))
      es.close()
    })
    es.onerror = () => {
      setState(s => s.status !== 'done' ? { ...s, status: 'error', error: 'Stream disconnected' } : s)
      es.close()
    }
  }, [])

  const reset = useCallback(() => {
    esRef.current?.close()
    setState(INITIAL)
  }, [])

  return { state, start, reset }
}

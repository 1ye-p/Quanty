/**
 * 轮询回测任务状态的 hook。
 * 每 2 秒查询一次 /backtests/jobs/{job_id}，完成或失败后自动停止。
 */
import { useCallback, useEffect, useRef } from 'react'
import { backtestsApi } from '@/lib/api'

interface JobPollerOptions {
  onComplete: (runId: string) => void
  onError: (error: string) => void
  intervalMs?: number
}

export function useJobPoller({ onComplete, onError, intervalMs = 2000 }: JobPollerOptions) {
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stop = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const start = useCallback(
    (jobId: string) => {
      stop()
      timerRef.current = setInterval(async () => {
        try {
          const job = await backtestsApi.pollJob(jobId)
          if (job.status === 'completed' && job.run_id) {
            stop()
            onComplete(job.run_id)
          } else if (job.status === 'failed') {
            stop()
            onError(job.error ?? '未知错误')
          }
          // status === 'running' → 继续轮询
        } catch {
          stop()
          onError('轮询任务状态失败，请刷新页面')
        }
      }, intervalMs)
    },
    [stop, onComplete, onError, intervalMs],
  )

  useEffect(() => stop, [stop])  // 组件卸载时清理

  return { start, stop }
}

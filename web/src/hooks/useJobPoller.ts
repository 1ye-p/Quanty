import { useQuery } from '@tanstack/react-query'

interface PollerOptions<T> {
  queryKey: readonly unknown[]
  queryFn: () => Promise<T>
  isDone: (data: T) => boolean
  interval?: number
  enabled?: boolean
}

/** Poll a query until isDone returns true, then stop. */
export function useJobPoller<T>({ queryKey, queryFn, isDone, interval = 2000, enabled = true }: PollerOptions<T>) {
  return useQuery({
    queryKey,
    queryFn,
    enabled,
    refetchInterval: (query) => {
      const data = query.state.data as T | undefined
      return data && isDone(data) ? false : interval
    },
  })
}

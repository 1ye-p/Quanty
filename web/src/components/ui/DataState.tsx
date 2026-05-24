import type { ReactNode } from 'react'

interface DataStateProps {
  isLoading?: boolean
  error?: unknown
  isEmpty?: boolean
  emptyText?: string
  children: ReactNode
  /** Custom loading component (defaults to skeleton) */
  loadingFallback?: ReactNode
  /** Custom error component */
  errorFallback?: (error: unknown) => ReactNode
}

function DefaultSkeleton() {
  return (
    <div className="animate-pulse space-y-3">
      <div className="h-4 bg-gray-200 rounded w-3/4" />
      <div className="h-4 bg-gray-200 rounded w-1/2" />
      <div className="h-4 bg-gray-200 rounded w-2/3" />
    </div>
  )
}

function DefaultEmpty({ text }: { text: string }) {
  return (
    <div className="text-center py-12 text-gray-400">
      <div className="text-4xl mb-2">📭</div>
      <div className="text-sm">{text}</div>
    </div>
  )
}

function DefaultError({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : String(error)
  return (
    <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-red-700 text-sm">
      <div className="font-medium mb-1">加载失败</div>
      <div className="text-red-600">{message}</div>
    </div>
  )
}

export function DataState({
  isLoading,
  error,
  isEmpty,
  emptyText = '暂无数据',
  children,
  loadingFallback,
  errorFallback,
}: DataStateProps) {
  if (isLoading) return <>{loadingFallback ?? <DefaultSkeleton />}</>
  if (error) return <>{errorFallback ? errorFallback(error) : <DefaultError error={error} />}</>
  if (isEmpty) return <DefaultEmpty text={emptyText} />
  return <>{children}</>
}

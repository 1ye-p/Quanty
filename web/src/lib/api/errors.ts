/**
 * cQuant API — Unified error handling.
 *
 * Provides typed error classes for different failure modes
 * and utility functions for error classification and user-facing messages.
 */

// ── Error codes ────────────────────────────────────────────────────────────────

export const ErrorCode = {
  // Network errors
  NETWORK_ERROR: 'NETWORK_ERROR',
  TIMEOUT: 'TIMEOUT',
  ABORTED: 'ABORTED',

  // HTTP errors
  BAD_REQUEST: 'BAD_REQUEST',
  UNAUTHORIZED: 'UNAUTHORIZED',
  FORBIDDEN: 'FORBIDDEN',
  NOT_FOUND: 'NOT_FOUND',
  CONFLICT: 'CONFLICT',
  UNPROCESSABLE: 'UNPROCESSABLE',
  RATE_LIMITED: 'RATE_LIMITED',
  SERVER_ERROR: 'SERVER_ERROR',
  SERVICE_UNAVAILABLE: 'SERVICE_UNAVAILABLE',

  // Client errors
  INVALID_RESPONSE: 'INVALID_RESPONSE',
  UNKNOWN: 'UNKNOWN',
} as const

export type ErrorCode = (typeof ErrorCode)[keyof typeof ErrorCode]

// ── Error classes ──────────────────────────────────────────────────────────────

/**
 * Base API error. All API errors extend this class.
 */
export class ApiError extends Error {
  /** HTTP status code (0 for network errors). */
  readonly status: number
  /** Machine-readable error code. */
  readonly code: ErrorCode
  /** Structured error details from the server. */
  readonly details?: unknown
  /** Whether this error can be retried. */
  readonly retryable: boolean

  constructor(
    message: string,
    options: {
      status?: number
      code?: ErrorCode
      details?: unknown
      retryable?: boolean
      cause?: Error
    } = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = options.status ?? 0
    this.code = options.code ?? ErrorCode.UNKNOWN
    this.details = options.details
    this.retryable = options.retryable ?? false
    if (options.cause) {
      ;(this as { cause?: Error }).cause = options.cause
    }
  }
}

/**
 * Connection failures — DNS, network down, CORS blocked, etc.
 */
export class NetworkError extends ApiError {
  constructor(message = '网络连接失败', cause?: Error) {
    super(message, {
      status: 0,
      code: ErrorCode.NETWORK_ERROR,
      retryable: true,
      cause,
    })
    this.name = 'NetworkError'
  }
}

/**
 * Request exceeded the configured timeout.
 */
export class TimeoutError extends ApiError {
  constructor(message = '请求超时', cause?: Error) {
    super(message, {
      status: 0,
      code: ErrorCode.TIMEOUT,
      retryable: true,
      cause,
    })
    this.name = 'TimeoutError'
  }
}

/**
 * Request was cancelled via AbortController.
 */
export class AbortError extends ApiError {
  constructor(message = '请求已取消', cause?: Error) {
    super(message, {
      status: 0,
      code: ErrorCode.ABORTED,
      retryable: false,
      cause,
    })
    this.name = 'AbortError'
  }
}

// ── Error mapping ──────────────────────────────────────────────────────────────

/**
 * Map HTTP status code to ErrorCode.
 */
export function statusCodeToErrorCode(status: number): ErrorCode {
  const map: Record<number, ErrorCode> = {
    400: ErrorCode.BAD_REQUEST,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    409: ErrorCode.CONFLICT,
    422: ErrorCode.UNPROCESSABLE,
    429: ErrorCode.RATE_LIMITED,
    500: ErrorCode.SERVER_ERROR,
    502: ErrorCode.SERVER_ERROR,
    503: ErrorCode.SERVICE_UNAVAILABLE,
    504: ErrorCode.SERVER_ERROR,
  }
  return map[status] ?? ErrorCode.UNKNOWN
}

/**
 * Build an ApiError from a fetch Response.
 */
export async function createApiErrorFromResponse(res: Response): Promise<ApiError> {
  let body: Record<string, unknown> | undefined
  try {
    body = await res.json()
  } catch {
    body = undefined
  }

  const detail = (body?.detail ?? body?.message) as string | undefined
  const message = detail ?? `HTTP ${res.status}`
  const code = statusCodeToErrorCode(res.status)
  const retryable = res.status === 429 || res.status >= 500

  return new ApiError(message, {
    status: res.status,
    code,
    details: body,
    retryable,
  })
}

// ── Error classification ───────────────────────────────────────────────────────

/**
 * Check if an error should be retried.
 */
export function isRetryableError(error: unknown): boolean {
  if (error instanceof ApiError) {
    return error.retryable
  }
  if (error instanceof DOMException && error.name === 'AbortError') {
    return false
  }
  // Network errors from fetch are typically TypeError
  if (error instanceof TypeError) {
    return true
  }
  return false
}

/**
 * Check if an error is a timeout.
 */
export function isTimeoutError(error: unknown): boolean {
  if (error instanceof TimeoutError) return true
  if (error instanceof DOMException && error.name === 'TimeoutError') return true
  if (error instanceof Error && error.message.toLowerCase().includes('timeout')) return true
  return false
}

/**
 * Check if an error is an abort.
 */
export function isAbortError(error: unknown): boolean {
  if (error instanceof AbortError) return true
  if (error instanceof DOMException && error.name === 'AbortError') return true
  return false
}

// ── User-facing messages ───────────────────────────────────────────────────────

/**
 * Get a user-friendly error message in Chinese.
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case ErrorCode.NETWORK_ERROR:
        return '网络连接失败，请检查网络设置'
      case ErrorCode.TIMEOUT:
        return '请求超时，请稍后重试'
      case ErrorCode.ABORTED:
        return '请求已取消'
      case ErrorCode.BAD_REQUEST:
        return error.message || '请求参数错误'
      case ErrorCode.UNAUTHORIZED:
        return '登录已过期，请重新登录'
      case ErrorCode.FORBIDDEN:
        return '没有权限执行此操作'
      case ErrorCode.NOT_FOUND:
        return '请求的资源不存在'
      case ErrorCode.CONFLICT:
        return '资源冲突，请刷新后重试'
      case ErrorCode.UNPROCESSABLE:
        return error.message || '请求数据格式错误'
      case ErrorCode.RATE_LIMITED:
        return '请求过于频繁，请稍后重试'
      case ErrorCode.SERVER_ERROR:
        return '服务器内部错误，请稍后重试'
      case ErrorCode.SERVICE_UNAVAILABLE:
        return '服务暂时不可用，请稍后重试'
      case ErrorCode.INVALID_RESPONSE:
        return '服务器返回数据格式错误'
      default:
        return error.message || '未知错误'
    }
  }

  if (isTimeoutError(error)) return '请求超时，请稍后重试'
  if (isAbortError(error)) return '请求已取消'
  if (error instanceof TypeError) return '网络连接失败，请检查网络设置'
  if (error instanceof Error) return error.message

  return '发生未知错误'
}

/**
 * Extract HTTP status from an error (0 if not available).
 */
export function getErrorStatus(error: unknown): number {
  if (error instanceof ApiError) return error.status
  return 0
}

/**
 * Extract error code from an error.
 */
export function getErrorCode(error: unknown): ErrorCode {
  if (error instanceof ApiError) return error.code
  return ErrorCode.UNKNOWN
}

/**
 * cQuant API — Unified client module.
 *
 * Re-exports error classes and client utilities for convenient imports.
 */

// Error classes and utilities
export {
  ApiError,
  NetworkError,
  TimeoutError,
  AbortError,
  ErrorCode,
  type ErrorCode as ErrorCodeType,
  statusCodeToErrorCode,
  createApiErrorFromResponse,
  isRetryableError,
  isTimeoutError,
  isAbortError,
  getErrorMessage,
  getErrorStatus,
  getErrorCode,
} from './errors'

// Client functions and types
export {
  request,
  requestWithRetry,
  api,
  type RequestConfig,
  type RetryConfig,
} from './client'

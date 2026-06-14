/**
 * cQuant API — Unified client module.
 *
 * Re-exports error classes, client utilities, and domain-specific API objects.
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

// Domain APIs
export { backtestsApi } from './backtests'
export { mlApi } from './ml'
export { factorsApi } from './factors'
export { strategiesApi } from './strategies'
export { optimizeApi } from './optimize'

// Domain types
export type {
  SectorLimit,
  FactorExposureLimit,
  ConstraintConfig,
  OptimizeRequest,
  OptimizeResult,
  CovarianceRequest,
  CovarianceResult,
} from './optimize'

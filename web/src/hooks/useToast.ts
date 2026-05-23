/**
 * 统一 Toast 通知 hook。
 * 封装 sonner 的 toast 函数，提供 success/error/info 三种样式。
 */
import { toast } from 'sonner'

export interface ToastActions {
  success: (message: string) => void
  error: (message: string) => void
  info: (message: string) => void
}

export function useToast(): ToastActions {
  return {
    success: (message: string) => toast.success(message),
    error: (message: string) => toast.error(message),
    info: (message: string) => toast.info(message),
  }
}

/**
 * Shared test utilities for page-level tests.
 */

import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { I18nextProvider } from 'react-i18next'
import type { ReactNode } from 'react'

// Initialize i18n for tests — use zh-CN to match production default
import './i18n'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import zhCN from './i18n/locales/zh-CN.json'

if (!i18n.isInitialized) {
  i18n.use(initReactI18next).init({
    lng: 'zh-CN',
    fallbackLng: 'zh-CN',
    resources: { 'zh-CN': { translation: zhCN } },
    interpolation: { escapeValue: false },
  })
}

/** Render a component with QueryClientProvider, MemoryRouter, and i18n wrappers. */
export function renderWithProviders(ui: ReactNode, { route = '/' } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          {ui}
        </MemoryRouter>
      </QueryClientProvider>
    </I18nextProvider>,
  )
}

/**
 * Shared test utilities for page-level tests.
 */

import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { I18nextProvider } from 'react-i18next'
import type { ReactNode } from 'react'

// Initialize i18n for tests — force zh-CN deterministically.
// NOTE: do NOT import './i18n' here. That module pulls in LanguageDetector, which
// under jsdom resolves navigator.language to en-US and initializes i18n *before*
// this block runs (ES imports are hoisted), leaving i18n.isInitialized true and
// defeating the zh-CN override below. Tests must render the zh-CN (production
// default) locale so assertions against Chinese strings are deterministic.
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
} else {
  // Defensive: if i18n was already initialized by another import path, force the
  // active language back to zh-CN and ensure the zh-CN resource bundle is loaded.
  if (!i18n.hasResourceBundle('zh-CN', 'translation')) {
    i18n.addResourceBundle('zh-CN', 'translation', zhCN)
  }
  i18n.changeLanguage('zh-CN')
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

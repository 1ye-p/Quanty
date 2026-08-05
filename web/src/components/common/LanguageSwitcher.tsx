import { useTranslation } from 'react-i18next'

const LANGUAGES = [
  { code: 'zh-CN', labelKey: 'common.layout.language_switcher.zh-CN' },
  { code: 'en-US', labelKey: 'common.layout.language_switcher.en-US' },
] as const

/**
 * Dropdown for switching the UI language between zh-CN and en-US.
 * Persists the selection to localStorage via i18next-browser-languagedetector.
 */
export function LanguageSwitcher() {
  const { t, i18n } = useTranslation()

  return (
    <select
      value={i18n.language}
      onChange={e => i18n.changeLanguage(e.target.value)}
      className="text-xs bg-transparent border border-gray-200 rounded px-2 py-1 text-gray-600 hover:border-gray-300 focus:outline-none focus:ring-1 focus:ring-brand-400"
      aria-label={t('common.layout.language_switcher.aria_label')}
    >
      {LANGUAGES.map(lang => (
        <option key={lang.code} value={lang.code}>
          {t(lang.labelKey)}
        </option>
      ))}
    </select>
  )
}

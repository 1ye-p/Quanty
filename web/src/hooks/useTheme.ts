import { useThemeStore } from '../stores/themeStore';

/** @deprecated Use useThemeStore directly */
export function useTheme() {
  const { mode, toggle, setMode } = useThemeStore();
  return { theme: mode, toggle, setTheme: setMode };
}

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ThemeState {
  mode: 'light' | 'dark';
  toggle: () => void;
  setMode: (mode: 'light' | 'dark') => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      mode: 'light',
      toggle: () => {
        const newMode = get().mode === 'light' ? 'dark' : 'light';
        set({ mode: newMode });
        document.documentElement.classList.toggle('dark', newMode === 'dark');
      },
      setMode: (mode) => {
        set({ mode });
        document.documentElement.classList.toggle('dark', mode === 'dark');
      },
    }),
    {
      name: 'cquant-theme',
      onRehydrateStorage: () => (state) => {
        if (state?.mode === 'dark') {
          document.documentElement.classList.add('dark');
        }
      },
    }
  )
);

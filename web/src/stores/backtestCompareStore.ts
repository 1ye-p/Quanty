import { create } from 'zustand';

interface BacktestCompareState {
  selectedIds: string[];
  toggleSelection: (id: string) => void;
  selectAll: (ids: string[]) => void;
  clearSelection: () => void;
}

const MAX_COMPARE = 5;

export const useBacktestCompareStore = create<BacktestCompareState>()((set, get) => ({
  selectedIds: [],
  toggleSelection: (id) => {
    const { selectedIds } = get();
    if (selectedIds.includes(id)) {
      set({ selectedIds: selectedIds.filter(i => i !== id) });
    } else {
      if (selectedIds.length >= MAX_COMPARE) return;
      set({ selectedIds: [...selectedIds, id] });
    }
  },
  selectAll: (ids) => set({ selectedIds: ids.slice(0, MAX_COMPARE) }),
  clearSelection: () => set({ selectedIds: [] }),
}));

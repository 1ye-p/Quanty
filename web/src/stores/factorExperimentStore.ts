import { create } from 'zustand';

interface FactorExperimentState {
  selectedFactors: string[];
  icResults: Record<string, number>;
  toggleFactor: (name: string) => void;
  selectFactors: (names: string[]) => void;
  clearSelection: () => void;
  setICResults: (results: Record<string, number>) => void;
  getSignificantFactors: (threshold: number) => string[];
  reset: () => void;
}

export const useFactorExperimentStore = create<FactorExperimentState>()((set, get) => ({
  selectedFactors: [],
  icResults: {},
  toggleFactor: (name) => {
    const { selectedFactors } = get();
    if (selectedFactors.includes(name)) {
      set({ selectedFactors: selectedFactors.filter(f => f !== name) });
    } else {
      set({ selectedFactors: [...selectedFactors, name] });
    }
  },
  selectFactors: (names) => set({ selectedFactors: names }),
  clearSelection: () => set({ selectedFactors: [] }),
  setICResults: (results) => set({ icResults: results }),
  getSignificantFactors: (threshold) => {
    const { icResults } = get();
    return Object.entries(icResults)
      .filter(([_, ic]) => Math.abs(ic) >= threshold)
      .map(([name]) => name);
  },
  reset: () => set({ selectedFactors: [], icResults: {} }),
}));

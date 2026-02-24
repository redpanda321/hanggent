/**
 * Plan History Sidebar Store
 * 
 * Manages the open/close state of the plan history sidebar.
 */

import { create } from 'zustand';

interface PlanHistorySidebarState {
  isOpen: boolean;
  showAllProjects: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
  setShowAllProjects: (show: boolean) => void;
  toggleShowAllProjects: () => void;
}

export const usePlanHistorySidebarStore = create<PlanHistorySidebarState>((set) => ({
  isOpen: false,
  showAllProjects: false,
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  toggle: () => set((state) => ({ isOpen: !state.isOpen })),
  setShowAllProjects: (show) => set({ showAllProjects: show }),
  toggleShowAllProjects: () => set((state) => ({ showAllProjects: !state.showAllProjects })),
}));

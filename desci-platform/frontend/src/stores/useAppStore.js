/**
 * Global App Store (Zustand)
 * Centralized state management for notices, wallet, and UI state.
 */
import { create } from 'zustand';

const useAppStore = create((set) => ({
  // --- Notices ---
  notices: [],
  setNotices: (notices) => set({ notices }),
  addNotice: (notice) =>
    set((state) => ({ notices: [notice, ...state.notices] })),
  removeNotice: (id) =>
    set((state) => ({
      notices: state.notices.filter((n) => n.id !== id),
    })),

  // --- Wallet ---
  wallet: { address: null, balance: 0 },
  setWallet: (wallet) =>
    set((state) => ({
      wallet: { ...state.wallet, ...wallet },
    })),

  // --- UI ---
  ui: { sidebarOpen: true, theme: 'light' },
  toggleSidebar: () =>
    set((state) => ({
      ui: { ...state.ui, sidebarOpen: !state.ui.sidebarOpen },
    })),
  setTheme: (theme) =>
    set((state) => ({
      ui: { ...state.ui, theme },
    })),
}));

export default useAppStore;

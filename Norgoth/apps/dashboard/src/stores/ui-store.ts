"use client";

import { create } from "zustand";

const NAV_SCROLL_KEY = "norgoth.sidebar.navScrollTop";

type UiState = {
  navScrollTop: number;
  commandPaletteOpen: boolean;
  commandPaletteQuery: string;
  setNavScrollTop: (top: number) => void;
  hydrateNavScroll: () => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setCommandPaletteQuery: (query: string) => void;
  toggleCommandPalette: () => void;
};

function readStoredScroll(): number {
  if (typeof window === "undefined") return 0;
  try {
    const raw = sessionStorage.getItem(NAV_SCROLL_KEY);
    if (raw == null) return 0;
    const top = Number(raw);
    return Number.isNaN(top) ? 0 : top;
  } catch {
    return 0;
  }
}

function writeStoredScroll(top: number) {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(NAV_SCROLL_KEY, String(top));
  } catch {
    // ignore
  }
}

export const useUiStore = create<UiState>((set, get) => ({
  navScrollTop: 0,
  commandPaletteOpen: false,
  commandPaletteQuery: "",
  setNavScrollTop: (top) => {
    writeStoredScroll(top);
    set({ navScrollTop: top });
  },
  hydrateNavScroll: () => {
    set({ navScrollTop: readStoredScroll() });
  },
  setCommandPaletteOpen: (open) =>
    set({
      commandPaletteOpen: open,
      commandPaletteQuery: open ? get().commandPaletteQuery : "",
    }),
  setCommandPaletteQuery: (query) => set({ commandPaletteQuery: query }),
  toggleCommandPalette: () =>
    set((state) => ({
      commandPaletteOpen: !state.commandPaletteOpen,
      commandPaletteQuery: state.commandPaletteOpen
        ? ""
        : state.commandPaletteQuery,
    })),
}));

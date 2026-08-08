"use client";

import { useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { CFormInput, CListGroup, CListGroupItem } from "@coreui/react";
import { CIcon } from "@coreui/icons-react";
import { cilSearch } from "@coreui/icons";
import { getSidebarNavItems } from "@/components/navigation/sidebar";
import { useUiStore } from "@/stores/ui-store";
import type { Locale } from "@/i18n/config";

type CommandPaletteProps = {
  lang: Locale;
};

export function CommandPalette({ lang }: CommandPaletteProps) {
  const router = useRouter();
  const open = useUiStore((s) => s.commandPaletteOpen);
  const query = useUiStore((s) => s.commandPaletteQuery);
  const setOpen = useUiStore((s) => s.setCommandPaletteOpen);
  const setQuery = useUiStore((s) => s.setCommandPaletteQuery);
  const toggle = useUiStore((s) => s.toggleCommandPalette);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        toggle();
      }
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [toggle, setOpen]);

  const items = useMemo(() => getSidebarNavItems(lang), [lang]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (item) =>
        item.label.toLowerCase().includes(q) ||
        item.group.toLowerCase().includes(q) ||
        item.href.toLowerCase().includes(q)
    );
  }, [items, query]);

  if (!open) return null;

  return (
    <div
      className="norgoth-command-backdrop"
      onClick={() => setOpen(false)}
      role="presentation"
    >
      <div
        className="norgoth-command-panel"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
      >
        <div className="p-3 border-bottom d-flex align-items-center gap-2">
          <CIcon icon={cilSearch} />
          <CFormInput
            autoFocus
            value={query}
            placeholder="Search features, pages, commands…"
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Command search"
          />
          <kbd className="small text-body-secondary">Esc</kbd>
        </div>
        <CListGroup flush className="overflow-auto flex-grow-1">
          {filtered.length === 0 ? (
            <CListGroupItem className="text-body-secondary">
              No matches
            </CListGroupItem>
          ) : (
            filtered.map((item) => (
              <CListGroupItem
                key={item.href}
                as="button"
                type="button"
                className="d-flex align-items-center justify-content-between text-start w-100"
                onClick={() => {
                  setOpen(false);
                  router.push(item.href);
                }}
              >
                <span className="d-flex align-items-center gap-2">
                  <CIcon icon={item.icon} />
                  {item.label}
                </span>
                <span className="small text-body-secondary">{item.group}</span>
              </CListGroupItem>
            ))
          )}
        </CListGroup>
      </div>
    </div>
  );
}

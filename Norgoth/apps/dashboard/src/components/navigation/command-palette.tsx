"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { CFormInput, CListGroup, CListGroupItem } from "@coreui/react";
import { CIcon } from "@coreui/icons-react";
import { cilSearch } from "@coreui/icons";
import {
  filterSearchEntries,
  formatSearchEntryLabel,
  getSearchEntries,
} from "@/lib/nav/search-entries";
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
  const [activeIndex, setActiveIndex] = useState(0);

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

  const entries = useMemo(() => getSearchEntries(lang), [lang]);

  const filtered = useMemo(
    () => filterSearchEntries(entries, query),
    [entries, query]
  );

  useEffect(() => {
    setActiveIndex(0);
  }, [query, open]);

  useEffect(() => {
    if (activeIndex >= filtered.length) {
      setActiveIndex(Math.max(0, filtered.length - 1));
    }
  }, [activeIndex, filtered.length]);

  function navigateTo(href: string) {
    setOpen(false);
    setQuery("");
    router.push(href);
  }

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
            placeholder="Search features and settings…"
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActiveIndex((i) =>
                  filtered.length === 0 ? 0 : Math.min(i + 1, filtered.length - 1)
                );
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActiveIndex((i) => Math.max(i - 1, 0));
              } else if (e.key === "Enter") {
                e.preventDefault();
                const target = filtered[activeIndex];
                if (target) navigateTo(target.href);
              }
            }}
            aria-label="Command search"
            aria-activedescendant={
              filtered[activeIndex]
                ? `command-item-${filtered[activeIndex].id}`
                : undefined
            }
          />
          <kbd className="small text-body-secondary">Esc</kbd>
        </div>
        <CListGroup flush className="overflow-auto flex-grow-1">
          {filtered.length === 0 ? (
            <CListGroupItem className="text-body-secondary">
              No matches
            </CListGroupItem>
          ) : (
            filtered.map((item, index) => (
              <CListGroupItem
                id={`command-item-${item.id}`}
                key={item.id}
                as="button"
                type="button"
                className={`d-flex align-items-center justify-content-between text-start w-100${
                  index === activeIndex ? " norgoth-command-active" : ""
                }`}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => navigateTo(item.href)}
              >
                <span className="d-flex align-items-center gap-2 min-w-0">
                  {item.icon ? <CIcon icon={item.icon} /> : null}
                  <span className="text-truncate">
                    {formatSearchEntryLabel(item)}
                  </span>
                </span>
                <span className="small text-body-secondary flex-shrink-0 ms-2">
                  {item.kind === "subfeature"
                    ? item.parentLabel ?? item.group
                    : item.group}
                </span>
              </CListGroupItem>
            ))
          )}
        </CListGroup>
      </div>
    </div>
  );
}

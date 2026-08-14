"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CFormInput } from "@coreui/react";
import { parseEmbedColor } from "@/lib/discord/message-payload";
import { placePopover } from "@/lib/place-popover";

type EmbedColorPickerProps = {
  value?: number | string | null;
  onChange: (hex: string) => void;
  label?: string;
};

const PRESETS = [
  "#5865f2", // Discord blurple
  "#57f287", // green
  "#fee75c", // yellow
  "#eb459e", // fuchsia
  "#ed4245", // red
  "#faa61a", // orange
  "#3498db", // blue
  "#9b59b6", // purple
  "#1abc9c", // teal
  "#e91e63", // pink
  "#95a5a6", // grey
  "#18181b", // near-black
];

const POPOVER_WIDTH = 220;
const POPOVER_HEIGHT_FALLBACK = 180;

function toHex(value: number | string | null | undefined): string {
  const parsed = parseEmbedColor(value);
  return parsed != null
    ? `#${parsed.toString(16).padStart(6, "0")}`
    : "#5865f2";
}

/**
 * Compact popout colour picker for Discord embed accent colours. Emits a
 * validated #RRGGBB string. Reusable across every embed editor.
 */
export function EmbedColorPicker({
  value,
  onChange,
  label = "Color",
}: EmbedColorPickerProps) {
  const [open, setOpen] = useState(false);
  const [hexInput, setHexInput] = useState(toHex(value));
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  const currentHex = toHex(value);

  useEffect(() => {
    setHexInput(currentHex);
  }, [currentHex]);

  const close = () => {
    setOpen(false);
    triggerRef.current?.focus();
  };

  useLayoutEffect(() => {
    if (!open) return;

    const update = () => {
      const trigger = triggerRef.current?.getBoundingClientRect();
      if (!trigger) return;
      const panel = panelRef.current?.getBoundingClientRect();
      const placed = placePopover(
        trigger,
        {
          width: panel?.width || POPOVER_WIDTH,
          height: panel?.height || POPOVER_HEIGHT_FALLBACK,
        },
        { width: window.innerWidth, height: window.innerHeight },
      );
      setCoords({ top: placed.top, left: placed.left });
    };

    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onMouse = (event: MouseEvent) => {
      const target = event.target as Node;
      if (triggerRef.current?.contains(target)) return;
      if (panelRef.current?.contains(target)) return;
      if (
        panelRef.current &&
        document.activeElement instanceof Node &&
        panelRef.current.contains(document.activeElement)
      ) {
        return;
      }
      close();
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        close();
      }
    };
    document.addEventListener("mousedown", onMouse);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onMouse);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const commitHex = (raw: string) => {
    setHexInput(raw);
    const parsed = parseEmbedColor(raw);
    if (parsed != null) {
      onChange(`#${parsed.toString(16).padStart(6, "0")}`);
    }
  };

  const panel =
    open && typeof document !== "undefined"
      ? createPortal(
          <div
            ref={panelRef}
            className="p-3 border rounded shadow bg-body"
            style={{
              position: "fixed",
              top: coords.top,
              left: coords.left,
              zIndex: 1080,
              width: POPOVER_WIDTH,
              maxWidth: "min(220px, calc(100vw - 16px))",
            }}
            role="dialog"
          >
            <div className="d-flex flex-wrap gap-2 mb-3">
              {PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  className="rounded border p-0"
                  style={{
                    width: 28,
                    height: 28,
                    backgroundColor: preset,
                    outline:
                      preset.toLowerCase() === currentHex.toLowerCase()
                        ? "2px solid var(--cui-primary)"
                        : "none",
                  }}
                  title={preset}
                  onClick={() => {
                    commitHex(preset);
                  }}
                />
              ))}
            </div>
            <div className="d-flex align-items-center gap-2">
              <CFormInput
                type="color"
                value={currentHex}
                onChange={(event) => commitHex(event.target.value)}
                style={{ width: 48, padding: 2 }}
                aria-label="Custom color"
              />
              <CFormInput
                value={hexInput}
                maxLength={7}
                placeholder="#RRGGBB"
                onChange={(event) => commitHex(event.target.value)}
                aria-label="Hex color value"
              />
            </div>
          </div>,
          document.body,
        )
      : null;

  return (
    <div className="position-relative">
      <button
        ref={triggerRef}
        type="button"
        className="btn btn-outline-secondary d-flex align-items-center gap-2"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="dialog"
        aria-expanded={open}
        title={`${label}: ${currentHex}`}
      >
        <span
          className="rounded border"
          style={{
            width: 20,
            height: 20,
            backgroundColor: currentHex,
            display: "inline-block",
          }}
        />
        <span className="small text-uppercase">{currentHex}</span>
      </button>
      {panel}
    </div>
  );
}

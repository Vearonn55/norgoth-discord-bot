"use client";

import { useEffect, useRef, useState } from "react";
import { CFormInput } from "@coreui/react";
import { parseEmbedColor } from "@/lib/discord/message-payload";

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
  const containerRef = useRef<HTMLDivElement | null>(null);

  const currentHex = toHex(value);

  useEffect(() => {
    setHexInput(currentHex);
  }, [currentHex]);

  useEffect(() => {
    if (!open) return;
    const handler = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const commitHex = (raw: string) => {
    setHexInput(raw);
    const parsed = parseEmbedColor(raw);
    if (parsed != null) {
      onChange(`#${parsed.toString(16).padStart(6, "0")}`);
    }
  };

  return (
    <div className="position-relative" ref={containerRef}>
      <button
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

      {open ? (
        <div
          className="position-absolute z-3 mt-1 p-3 border rounded shadow bg-body"
          style={{ minWidth: 220 }}
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
        </div>
      ) : null}
    </div>
  );
}

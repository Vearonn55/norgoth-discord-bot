"use client";

import { CFormInput } from "@coreui/react";
import {
  useEffect,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
} from "react";

export type NumberInputProps = {
  value: number;
  /** Restored when the field is left empty on commit. */
  defaultValue: number;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  id?: string;
  className?: string;
  "aria-label"?: string;
  /** Called with the normalized number after commit (blur / Enter). */
  onCommit: (value: number) => void;
  /** Optional live draft updates while typing (committed values only if desired). */
  onChange?: (value: number | null) => void;
};

function allowsDecimal(step: number | undefined): boolean {
  if (step == null) return false;
  return !Number.isInteger(step);
}

function sanitizeDraft(raw: string, decimal: boolean): string {
  if (raw === "") return "";
  if (decimal) {
    // Allow intermediate "1." while typing.
    let cleaned = raw.replace(/[^\d.]/g, "");
    const firstDot = cleaned.indexOf(".");
    if (firstDot !== -1) {
      cleaned =
        cleaned.slice(0, firstDot + 1) +
        cleaned.slice(firstDot + 1).replace(/\./g, "");
    }
    return cleaned;
  }
  return raw.replace(/\D/g, "");
}

function normalizeCommitted(
  draft: string,
  {
    defaultValue,
    min,
    max,
    decimal,
  }: {
    defaultValue: number;
    min?: number;
    max?: number;
    decimal: boolean;
  }
): number {
  if (draft.trim() === "" || draft.trim() === ".") {
    return defaultValue;
  }
  const parsed = decimal ? Number.parseFloat(draft) : Number.parseInt(draft, 10);
  if (!Number.isFinite(parsed)) {
    return defaultValue;
  }
  let next = parsed;
  if (min != null) next = Math.max(min, next);
  if (max != null) next = Math.min(max, next);
  return decimal ? next : Math.trunc(next);
}

/**
 * Integer/decimal settings input that allows a temporary empty string while
 * editing. Empty commit restores ``defaultValue``. Never uses Number("").
 */
export function NumberInput({
  value,
  defaultValue,
  min,
  max,
  step = 1,
  disabled = false,
  id,
  className,
  "aria-label": ariaLabel,
  onCommit,
  onChange,
}: NumberInputProps) {
  const decimal = allowsDecimal(step);
  const [draft, setDraft] = useState(String(value));
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (!focused) {
      setDraft(String(value));
    }
  }, [value, focused]);

  function commit(raw: string) {
    const next = normalizeCommitted(raw, {
      defaultValue,
      min,
      max,
      decimal,
    });
    setDraft(String(next));
    onCommit(next);
    onChange?.(next);
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const nextDraft = sanitizeDraft(event.target.value, decimal);
    setDraft(nextDraft);
    if (nextDraft === "" || nextDraft === ".") {
      onChange?.(null);
      return;
    }
    const parsed = decimal
      ? Number.parseFloat(nextDraft)
      : Number.parseInt(nextDraft, 10);
    if (Number.isFinite(parsed)) {
      onChange?.(parsed);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.currentTarget.blur();
    }
  }

  return (
    <CFormInput
      id={id}
      type="text"
      inputMode={decimal ? "decimal" : "numeric"}
      pattern={decimal ? "[0-9]*\\.?[0-9]*" : "[0-9]*"}
      className={["norgoth-number-input", className].filter(Boolean).join(" ")}
      value={draft}
      disabled={disabled}
      aria-label={ariaLabel}
      min={min}
      max={max}
      step={step}
      onFocus={() => setFocused(true)}
      onBlur={() => {
        setFocused(false);
        commit(draft);
      }}
      onKeyDown={handleKeyDown}
      onChange={handleChange}
    />
  );
}

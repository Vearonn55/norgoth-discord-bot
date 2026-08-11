"use client";

import { CFormSwitch } from "@coreui/react";

type SwitchProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  /** Visual size. "lg" is used for prominent feature toggles. */
  size?: "md" | "lg";
  id?: string;
  "aria-label"?: string;
};

export function Switch({
  checked,
  onChange,
  disabled = false,
  size = "md",
  id,
  "aria-label": ariaLabel,
}: SwitchProps) {
  return (
    <span
      className={["norgoth-switch", size === "lg" ? "norgoth-switch-lg" : ""]
        .filter(Boolean)
        .join(" ")}
    >
      <CFormSwitch
        id={id}
        checked={checked}
        disabled={disabled}
        aria-label={ariaLabel}
        onChange={(event) => onChange(event.target.checked)}
      />
    </span>
  );
}

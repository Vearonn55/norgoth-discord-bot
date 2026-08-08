"use client";

import {
  ROLE_MENU_STYLE_SWATCHES,
  ROLE_MENU_STYLES,
  type RoleMenuStyle,
} from "@/lib/discord/role-menu-modes";

type DiscordButtonStylePickerProps = {
  value: RoleMenuStyle;
  onChange: (style: RoleMenuStyle) => void;
  disabled?: boolean;
};

export function DiscordButtonStylePicker({
  value,
  onChange,
  disabled = false,
}: DiscordButtonStylePickerProps) {
  return (
    <div
      className="norgoth-discord-button-style-picker d-flex flex-wrap gap-2"
      role="radiogroup"
      aria-label="Button color"
    >
      {ROLE_MENU_STYLES.map((style) => {
        const swatch = ROLE_MENU_STYLE_SWATCHES[style];
        const selected = value === style;
        return (
          <button
            key={style}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            className={[
              "norgoth-discord-style-swatch btn btn-sm",
              selected ? "norgoth-discord-style-swatch-active" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            style={{
              background: swatch.background,
              color: swatch.color,
              borderColor: selected ? "#fff" : "transparent",
              minWidth: "5.5rem",
              fontWeight: 600,
            }}
            onClick={() => onChange(style)}
            title={swatch.label}
          >
            {swatch.label}
          </button>
        );
      })}
    </div>
  );
}

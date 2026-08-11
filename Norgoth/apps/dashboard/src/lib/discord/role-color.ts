/**
 * Discord role color helpers.
 * Discord API may send integer (0xRRGGBB) or "#RRGGBB" / "RRGGBB".
 */

export function normalizeDiscordRoleColor(
  color: string | number | null | undefined
): string | null {
  if (color == null || color === "" || color === 0 || color === "0") {
    return null;
  }

  if (typeof color === "number") {
    if (color <= 0) return null;
    return `#${color.toString(16).padStart(6, "0")}`;
  }

  const raw = color.trim();
  if (!raw || raw === "#000000" || raw === "000000") return null;

  if (raw.startsWith("#")) {
    return raw.length === 7 ? raw : null;
  }

  if (/^[0-9a-fA-F]{6}$/.test(raw)) {
    return `#${raw}`;
  }

  const asInt = Number(raw);
  if (!Number.isNaN(asInt) && asInt > 0) {
    return `#${asInt.toString(16).padStart(6, "0")}`;
  }

  return null;
}

/** Relative luminance for WCAG-ish contrast pick. */
function luminance(hex: string): number {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16) / 255;
  const g = parseInt(h.slice(2, 4), 16) / 255;
  const b = parseInt(h.slice(4, 6), 16) / 255;
  const lin = (c: number) =>
    c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

export function contrastingForeground(hex: string): string {
  return luminance(hex) > 0.45 ? "#0b0e14" : "#f1f4fa";
}

export function roleColorStyles(color: string | number | null | undefined): {
  background: string;
  color: string;
  borderColor: string;
} | null {
  const hex = normalizeDiscordRoleColor(color);
  if (!hex) return null;
  return {
    background: `${hex}33`,
    color: contrastingForeground(hex),
    borderColor: `${hex}99`,
  };
}

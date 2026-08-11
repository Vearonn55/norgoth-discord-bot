export const ROLE_MENU_MODES = ["toggle", "give", "take"] as const;
export type RoleMenuMode = (typeof ROLE_MENU_MODES)[number];

export const ROLE_MENU_STYLES = [
  "primary",
  "secondary",
  "success",
  "danger",
] as const;
export type RoleMenuStyle = (typeof ROLE_MENU_STYLES)[number];

export const ROLE_MENU_INTERACTIONS = ["buttons", "select", "reactions"] as const;
export type RoleMenuInteraction = (typeof ROLE_MENU_INTERACTIONS)[number];

export const BUTTON_STYLE_API: Record<RoleMenuStyle, number> = {
  primary: 1,
  secondary: 2,
  success: 3,
  danger: 4,
};

/** User-facing labels — keep internal wire values unchanged. */
export const ROLE_MENU_INTERACTION_LABELS: Record<
  RoleMenuInteraction,
  string
> = {
  buttons: "Button",
  select: "Dropdown List",
  reactions: "Emoji Reaction",
};

export const ROLE_MENU_INTERACTION_HELP: Record<RoleMenuInteraction, string> = {
  buttons: "Members click colored buttons to change roles.",
  select: "Members pick a role from a dropdown list.",
  reactions: "Members react with an emoji on the posted message.",
};

export const ROLE_MENU_MODE_LABELS: Record<RoleMenuMode, string> = {
  toggle: "Toggle",
  give: "Give",
  take: "Take",
};

export const ROLE_MENU_MODE_HELP: Record<RoleMenuMode, string> = {
  toggle: "Adds the role if missing, removes it if already assigned.",
  give: "Only adds the role. Does not remove it later from this control.",
  take: "Only removes the role. Does not grant it.",
};

export const ROLE_MENU_STYLE_SWATCHES: Record<
  RoleMenuStyle,
  { label: string; background: string; color: string }
> = {
  primary: {
    label: "Blue",
    background: "#5865F2",
    color: "#ffffff",
  },
  secondary: {
    label: "Grey",
    background: "#4e5058",
    color: "#ffffff",
  },
  success: {
    label: "Green",
    background: "#248046",
    color: "#ffffff",
  },
  danger: {
    label: "Red",
    background: "#DA373C",
    color: "#ffffff",
  },
};

export function roleMenuInteractionLabel(
  value: string | null | undefined
): string {
  if (value && isRoleMenuInteraction(value)) {
    return ROLE_MENU_INTERACTION_LABELS[value];
  }
  return ROLE_MENU_INTERACTION_LABELS.buttons;
}

export function isRoleMenuMode(value: string): value is RoleMenuMode {
  return (ROLE_MENU_MODES as readonly string[]).includes(value);
}

export function isRoleMenuStyle(value: string): value is RoleMenuStyle {
  return (ROLE_MENU_STYLES as readonly string[]).includes(value);
}

export function isRoleMenuInteraction(
  value: string
): value is RoleMenuInteraction {
  return (ROLE_MENU_INTERACTIONS as readonly string[]).includes(value);
}

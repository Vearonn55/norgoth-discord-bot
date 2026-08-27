export type SetupState = "not_installed" | "installed";

export type SetupAction = "install" | "open";

export function setupStateAction(state: SetupState): SetupAction {
  switch (state) {
    case "not_installed":
      return "install";
    case "installed":
      return "open";
  }
}

export function isSetupState(value: unknown): value is SetupState {
  return value === "not_installed" || value === "installed";
}

/** Derive binary install state from API fields, tolerating stale 3-way values. */
export function resolveSetupState(input: {
  setup_state?: unknown;
  bot_installed?: boolean;
}): SetupState {
  // bot_installed is the authoritative install signal for the selector.
  if (typeof input.bot_installed === "boolean") {
    return input.bot_installed ? "installed" : "not_installed";
  }
  if (isSetupState(input.setup_state)) {
    return input.setup_state;
  }
  // Legacy feature-config values without bot_installed cannot imply install.
  return "not_installed";
}

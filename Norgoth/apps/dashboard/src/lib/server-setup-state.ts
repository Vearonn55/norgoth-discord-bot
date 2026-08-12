export type SetupState = "not_installed" | "not_configured" | "configured";

export type SetupAction = "install" | "configure" | "open";

export function setupStateAction(state: SetupState): SetupAction {
  switch (state) {
    case "not_installed":
      return "install";
    case "not_configured":
      return "configure";
    case "configured":
      return "open";
  }
}

export function isSetupState(value: unknown): value is SetupState {
  return (
    value === "not_installed" ||
    value === "not_configured" ||
    value === "configured"
  );
}

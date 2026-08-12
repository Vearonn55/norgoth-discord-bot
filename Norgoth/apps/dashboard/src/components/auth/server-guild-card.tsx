"use client";

import { botInviteHref } from "@/lib/bot-invite";
import {
  setupStateAction,
  type SetupState,
} from "@/lib/server-setup-state";
import { GuildIcon } from "@/components/ui/guild-icon";

export type ServerGuildItem = {
  id: string;
  name: string;
  icon?: string | null;
  icon_url: string | null;
  bot_installed: boolean;
  owner?: boolean;
  permissions?: string;
  role_label?: string;
  setup_state?: SetupState;
  manageable?: boolean;
};

export type ServerGuildCopy = {
  notInstalled: string;
  notConfigured: string;
  configured: string;
  open: string;
  continueSetup: string;
  installNorBot: string;
  addNorgoth: string;
  roleOwner: string;
  roleAdministrator: string;
  roleManageServer: string;
};

function localizeRole(label: string | undefined, copy: ServerGuildCopy): string {
  switch (label) {
    case "Owner":
      return copy.roleOwner;
    case "Administrator":
      return copy.roleAdministrator;
    default:
      return copy.roleManageServer;
  }
}

function statusLabel(state: SetupState, copy: ServerGuildCopy): string {
  switch (state) {
    case "configured":
      return copy.configured;
    case "not_configured":
      return copy.notConfigured;
    default:
      return copy.notInstalled;
  }
}

function actionLabel(state: SetupState, copy: ServerGuildCopy): string {
  switch (setupStateAction(state)) {
    case "open":
      return copy.open;
    case "configure":
      return copy.continueSetup;
    default:
      return copy.installNorBot || copy.addNorgoth;
  }
}

export function ServerGuildCard({
  server,
  selected,
  copy,
  onOpen,
}: {
  server: ServerGuildItem;
  selected: boolean;
  copy: ServerGuildCopy;
  onOpen: (server: ServerGuildItem) => void;
}) {
  const setupState: SetupState =
    server.setup_state ??
    (server.bot_installed ? "not_configured" : "not_installed");
  const accent =
    setupState === "configured" ? "var(--cui-success)" : "var(--cui-danger)";
  const status = statusLabel(setupState, copy);
  const action = actionLabel(setupState, copy);
  const role = localizeRole(server.role_label, copy);
  const installed = setupState !== "not_installed";

  return (
    <button
      type="button"
      className={`norgoth-mini-card norgoth-server-guild-card text-start d-flex flex-column gap-2 p-3 border-0 w-100 h-100${
        selected ? " is-selected" : ""
      }`}
      style={{ ["--norgoth-section-accent" as string]: accent }}
      onClick={() => {
        if (!installed) return;
        onOpen(server);
      }}
      aria-current={selected ? "true" : undefined}
      aria-disabled={installed ? undefined : true}
      aria-label={`${server.name}, ${status}`}
    >
      <span className="d-flex align-items-center gap-3 w-100">
        <GuildIcon url={server.icon_url} name={server.name} size={40} />
        <span className="flex-grow-1 min-w-0">
          <span className="d-block fw-semibold text-truncate">{server.name}</span>
          <span className="d-inline-flex align-items-center gap-2 mt-1 flex-wrap">
            <span className="badge text-bg-secondary fw-normal">{role}</span>
            <span className="norgoth-mini-card-status small d-inline-flex align-items-center gap-2">
              <span
                className="norgoth-mini-card-dot"
                style={{ background: accent }}
                aria-hidden="true"
              />
              {status}
            </span>
          </span>
        </span>
      </span>
      <span className="d-flex justify-content-end w-100">
        {setupState === "not_installed" ? (
          <a
            href={botInviteHref(server.id)}
            className="btn btn-sm btn-primary norgoth-server-guild-action"
            onClick={(event) => event.stopPropagation()}
          >
            {action}
          </a>
        ) : (
          <span className="small norgoth-server-guild-action d-inline-flex align-items-center">
            {action}
          </span>
        )}
      </span>
    </button>
  );
}



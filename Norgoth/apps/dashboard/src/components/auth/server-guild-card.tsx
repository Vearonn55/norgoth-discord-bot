"use client";

import { botInviteHref } from "@/lib/bot-invite";
import {
  resolveSetupState,
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
  installed: string;
  manage: string;
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
  return state === "installed" ? copy.installed : copy.notInstalled;
}

function actionLabel(state: SetupState, copy: ServerGuildCopy): string {
  return setupStateAction(state) === "open"
    ? copy.manage
    : copy.installNorBot || copy.addNorgoth;
}

function cardClassName(selected: boolean): string {
  return `norgoth-mini-card norgoth-server-guild-card text-start d-flex flex-column gap-2 p-3 border-0 w-100 h-100${
    selected ? " is-selected" : ""
  }`;
}

const actionClassName =
  "btn btn-sm norgoth-server-guild-action d-inline-flex align-items-center justify-content-center";

export function ServerGuildCard({
  server,
  selected,
  copy,
  onOpen,
  onInstall,
}: {
  server: ServerGuildItem;
  selected: boolean;
  copy: ServerGuildCopy;
  onOpen: (server: ServerGuildItem) => void;
  /** Fired when the user starts guild install (new tab). */
  onInstall?: (server: ServerGuildItem) => void;
}) {
  const setupState = resolveSetupState(server);
  const installed = setupState === "installed";
  const accent = installed ? "var(--cui-success)" : "var(--cui-danger)";
  const status = statusLabel(setupState, copy);
  const action = actionLabel(setupState, copy);
  const role = localizeRole(server.role_label, copy);
  const installAttr = installed ? "installed" : "not_installed";
  const style = { ["--norgoth-section-accent" as string]: accent };
  const ariaLabel = `${server.name}, ${status}`;

  const header = (
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
  );

  if (!installed) {
    return (
      <div
        className={cardClassName(selected)}
        style={style}
        data-install={installAttr}
        aria-label={ariaLabel}
        role="group"
      >
        {header}
        <span className="d-flex justify-content-end w-100 mt-auto">
          <a
            href={botInviteHref(server.id)}
            target="_blank"
            rel="noopener noreferrer"
            className={`${actionClassName} btn-primary`}
            aria-label={`${action} ${server.name}`}
            onClick={() => {
              onInstall?.(server);
            }}
          >
            {action}
          </a>
        </span>
      </div>
    );
  }

  return (
    <div
      className={cardClassName(selected)}
      style={style}
      data-install={installAttr}
      aria-label={ariaLabel}
      aria-current={selected ? "true" : undefined}
      role="group"
    >
      {header}
      <span className="d-flex justify-content-end w-100 mt-auto">
        <button
          type="button"
          className={`${actionClassName} btn-success`}
          aria-label={`${action} ${server.name}`}
          onClick={() => onOpen(server)}
        >
          {action}
        </button>
      </span>
    </div>
  );
}

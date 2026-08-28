import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ServerGuildCard } from "@/components/auth/server-guild-card";

vi.mock("@/lib/bot-invite", () => ({
  botInviteHref: (guildId: string) =>
    `https://discord.com/oauth2/invite?guild_id=${guildId}`,
}));

const copy = {
  notInstalled: "Not Installed",
  installed: "Installed",
  manage: "Manage",
  install: "Install",
  installAria: "Install NorBot on {name}",
  addNorgoth: "Install",
  roleOwner: "Owner",
  roleAdministrator: "Administrator",
  roleManageServer: "Manage Server",
};

describe("ServerGuildCard", () => {
  it("renders Installed status with Manage success button", () => {
    const html = renderToStaticMarkup(
      <ServerGuildCard
        server={{
          id: "111",
          name: "Ready Guild",
          icon_url: null,
          bot_installed: true,
          setup_state: "installed",
          role_label: "Owner",
        }}
        selected={false}
        copy={copy}
        onOpen={() => undefined}
      />,
    );

    expect(html).toContain("Installed");
    expect(html).not.toContain("Not Installed");
    expect(html).not.toContain("Not configured");
    expect(html).not.toContain("Open Command Center");
    expect(html).toContain('data-install="installed"');
    expect(html).toContain("var(--cui-success)");
    expect(html).toContain("Manage");
    expect(html).toContain("btn-success");
    expect(html).toContain('role="group"');
    expect(html).toContain("<button");
    expect(html).toContain('aria-label="Manage Ready Guild"');
  });

  it("renders Not Installed status with short Install label and branded aria", () => {
    const html = renderToStaticMarkup(
      <ServerGuildCard
        server={{
          id: "222",
          name: "Needs Install",
          icon_url: null,
          bot_installed: false,
          setup_state: "not_installed",
          role_label: "Manage Server",
        }}
        selected={false}
        copy={copy}
        onOpen={() => undefined}
      />,
    );

    expect(html).toContain("Not Installed");
    expect(html).toContain(">Install<");
    expect(html).not.toContain(">Install NorBot<");
    expect(html).toContain('data-install="not_installed"');
    expect(html).toContain("var(--cui-danger)");
    expect(html).toContain("guild_id=222");
    expect(html).toContain("btn-primary");
    expect(html).toContain('role="group"');
    expect(html).not.toContain("<button");
    expect(html).toContain("justify-content-center");
    expect(html).toContain('aria-label="Install NorBot on Needs Install"');
  });

  it("treats legacy not_configured setup_state as installed when bot is present", () => {
    const html = renderToStaticMarkup(
      <ServerGuildCard
        server={{
          id: "333",
          name: "Legacy",
          icon_url: null,
          bot_installed: true,
          setup_state: "not_configured" as unknown as "installed",
          role_label: "Administrator",
        }}
        selected={false}
        copy={copy}
        onOpen={() => undefined}
      />,
    );

    expect(html).toContain("Installed");
    expect(html).toContain("Manage");
    expect(html).toContain('data-install="installed"');
    expect(html).not.toContain("Not configured");
  });
});

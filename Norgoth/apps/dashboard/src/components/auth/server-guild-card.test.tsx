import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ServerGuildCard } from "@/components/auth/server-guild-card";

vi.mock("@/lib/bot-invite", () => ({
  botInviteHref: (guildId: string) => `https://discord.com/oauth2/invite?guild_id=${guildId}`,
}));

const copy = {
  notInstalled: "Not Installed",
  installed: "Installed",
  open: "Open Command Center",
  installNorBot: "Install NorBot",
  addNorgoth: "Install NorBot",
  roleOwner: "Owner",
  roleAdministrator: "Administrator",
  roleManageServer: "Manage Server",
};

describe("ServerGuildCard", () => {
  it("renders Installed status with green accent for bot members", () => {
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
      />
    );

    expect(html).toContain("Installed");
    expect(html).not.toContain("Not Installed");
    expect(html).not.toContain("Not configured");
    expect(html).toContain('data-install="installed"');
    expect(html).toContain("var(--cui-success)");
    expect(html).toContain("Open Command Center");
    expect(html).toContain("<button");
  });

  it("renders Not Installed status with install link and no nested button", () => {
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
      />
    );

    expect(html).toContain("Not Installed");
    expect(html).toContain("Install NorBot");
    expect(html).toContain('data-install="not_installed"');
    expect(html).toContain("var(--cui-danger)");
    expect(html).toContain("guild_id=222");
    expect(html).toContain('role="group"');
    expect(html).not.toContain("<button");
    expect(html).toContain("justify-content-center");
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
      />
    );

    expect(html).toContain("Installed");
    expect(html).toContain('data-install="installed"');
    expect(html).not.toContain("Not configured");
  });
});

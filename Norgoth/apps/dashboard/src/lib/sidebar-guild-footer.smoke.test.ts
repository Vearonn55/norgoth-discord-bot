import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = resolve(__dirname, "..");
const sidebarPath = resolve(root, "components/navigation/sidebar.tsx");
const cssPath = resolve(root, "app/globals.css");
const shellPath = resolve(root, "components/layout/app-shell.tsx");

function footerSource(src: string): string {
  const start = src.indexOf("function SidebarGuildFooter");
  expect(start).toBeGreaterThan(-1);
  return src.slice(start);
}

describe("sidebar guild footer hit area", () => {
  it("wraps a single full-width Link inside a padded-zero footer", () => {
    const src = readFileSync(sidebarPath, "utf8");
    const footer = footerSource(src);

    expect(src).toContain('<CSidebarFooter className="border-top p-0">');
    expect(src).toContain("<SidebarGuildFooter lang={lang} labels={labels} />");
    expect(src.match(/<CSidebarFooter/g)).toHaveLength(1);

    expect(footer).toContain('href={`/${lang}/servers`}');
    expect(footer).toContain("scroll={false}");
    expect(footer).toContain("norgoth-sidebar-guild");
    expect(footer).toContain("w-100");
    expect(footer).toContain("flex-grow-1 min-w-0");
    expect(footer).toContain("<GuildIcon");
    expect(footer).toContain("{name}");
    expect(footer).toContain("{labels.serverSelection}");
    expect(footer).toContain(
      "aria-label={`${labels.serverSelection}: ${name}`}"
    );

    expect(footer.match(/<Link/g)).toHaveLength(1);
    expect(footer).not.toContain("onClick");
    expect(footer).not.toContain("onKeyDown");
    expect(footer).not.toMatch(/<button/);
    expect(footer).not.toContain("CDropdown");
    expect(footer).not.toMatch(/chevron|caret|cilChevron/i);
  });

  it("keeps nav links as separate hit targets and does not collapse the rail", () => {
    const src = readFileSync(sidebarPath, "utf8");
    expect(src).toContain("CNavLink as={Link}");
    expect(src).toContain('<CSidebar className="norgoth-sidebar" colorScheme="dark" visible>');
    expect(src).not.toMatch(/\bnarrow\b/);
    expect(src).not.toContain("unfoldable");
  });
});

describe("sidebar guild footer CSS", () => {
  it("stretches the footer trigger and keeps focus chrome inside the section", () => {
    const css = readFileSync(cssPath, "utf8");
    const footerBlockStart = css.indexOf(".norgoth-sidebar .sidebar-footer {");
    const guildBlockStart = css.indexOf(".norgoth-sidebar-guild {");
    expect(footerBlockStart).toBeGreaterThan(-1);
    expect(guildBlockStart).toBeGreaterThan(-1);

    const footerBlock = css.slice(
      footerBlockStart,
      css.indexOf("}", footerBlockStart) + 1
    );
    const guildBlock = css.slice(
      guildBlockStart,
      css.indexOf("}", guildBlockStart) + 1
    );

    expect(footerBlock).toContain("flex-shrink: 0");
    expect(footerBlock).toContain("width: 100%");
    expect(guildBlock).toContain("width: 100%");
    expect(guildBlock).toContain("cursor: pointer");
    expect(guildBlock).not.toContain("position: absolute");

    expect(css).toContain(".norgoth-sidebar-guild:hover");
    expect(css).toContain(".norgoth-sidebar-guild:focus-visible");
    expect(css).toContain(".norgoth-sidebar-guild:active");
    expect(css).toContain("outline-offset: -2px");

    const focusBlockStart = css.indexOf(
      ".norgoth-sidebar-guild:focus-visible {"
    );
    expect(focusBlockStart).toBeGreaterThan(-1);
    const focusBlock = css.slice(
      focusBlockStart,
      css.indexOf("}", focusBlockStart) + 1
    );
    expect(focusBlock).not.toContain("outline: none");
  });
});

describe("server selector navigation", () => {
  it("still hides the sidebar on the servers page", () => {
    const src = readFileSync(shellPath, "utf8");
    expect(src).toContain("function isServerSelector");
    expect(src).toContain("norgoth-server-selector");
    expect(src).toContain("/\\/servers\\/?$/");
  });
});

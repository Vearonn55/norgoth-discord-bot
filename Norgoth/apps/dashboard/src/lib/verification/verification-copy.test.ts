import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";

const EN_WARNING =
  "Save channels and roles in Verification Settings before public verification can work. Turning the master switch on alone does not publish a working authorize link.";
const TR_WARNING =
  "Genel doğrulamanın çalışması için önce Doğrulama Ayarları'nda kanalları ve rolleri kaydedin. Yalnızca ana anahtarı açmak, çalışan bir authorize bağlantısı yayınlamaz.";

const viewPath = resolve(
  __dirname,
  "../../components/verification/member-verification-view.tsx",
);

describe("verification bindings warning copy", () => {
  it("keeps the English warning unchanged and has no interpolation tokens", () => {
    expect(en.verificationPage.bindingsWarning).toBe(EN_WARNING);
    expect(en.verificationPage.bindingsWarning).not.toContain("{");
  });

  it("stores the approved Turkish warning with Turkish characters and no interpolation tokens", () => {
    expect(tr.verificationPage.bindingsWarning).toBe(TR_WARNING);
    expect(tr.verificationPage.bindingsWarning).toContain("ş");
    expect(tr.verificationPage.bindingsWarning).toContain("ğ");
    expect(tr.verificationPage.bindingsWarning).toContain("ı");
    expect(tr.verificationPage.bindingsWarning).not.toContain("{");
  });

  it("wires MemberVerificationView to the dictionary key instead of hard-coded English", () => {
    const src = readFileSync(viewPath, "utf8");
    expect(src).toContain("useLocaleDict");
    expect(src).toContain("dict.verificationPage");
    expect(src).toContain("d.bindingsWarning");
    expect(src).not.toContain(EN_WARNING);
    expect(src).not.toContain("Save channels and roles in Verification Settings");
  });
});

describe("verification settings modal save close", () => {
  it("closes after a successful save and does not wait on publish", () => {
    const src = readFileSync(
      resolve(
        __dirname,
        "../../components/verification/verification-settings-modal.tsx",
      ),
      "utf8",
    );
    expect(src).toContain("const result = await save(guildId);");
    expect(src).toContain("onClose();");
    expect(src).toContain("void publishPanel(guildId, lang)");
    expect(src).not.toContain("saveAndPublish");
    expect(src).not.toContain("await loadConfig(guildId);");
  });
});

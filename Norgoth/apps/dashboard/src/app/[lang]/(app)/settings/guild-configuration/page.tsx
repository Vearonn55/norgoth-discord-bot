import Link from "next/link";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { VerificationSettingsPanel } from "@/components/verification/verification-settings-panel";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function GuildConfigurationPage({
  params,
}: PageProps<"/[lang]/settings/guild-configuration">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
        <PageHeader
          title="Guild Configuration"
          description="Member verification policy: channels, roles, account-age minimum, VPN and shared-IP protection."
          actions={
            <Button asChild variant="secondary">
              <Link href={`/${lang}/settings`}>Back to Settings</Link>
            </Button>
          }
        />

        <VerificationSettingsPanel />
      </div>
  );
}

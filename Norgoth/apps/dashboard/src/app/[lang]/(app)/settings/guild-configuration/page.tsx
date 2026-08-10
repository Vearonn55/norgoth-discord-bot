import Link from "next/link";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { VerificationSettingsForm } from "@/components/verification/verification-settings-form";
import { getDictionary, hasLocale } from "../../../dictionaries";

/**
 * Legacy standalone route. Verification settings now live in the Verification
 * Settings modal on the Member Verification page; this thin wrapper is kept for
 * backwards-compatible bookmarks and is flagged for later removal.
 */
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
              <Link href={`/${lang}/community/onboarding`}>Member Verification</Link>
            </Button>
          }
        />

        <VerificationSettingsForm />
      </div>
  );
}

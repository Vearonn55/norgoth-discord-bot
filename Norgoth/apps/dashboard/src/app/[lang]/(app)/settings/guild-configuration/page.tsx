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

  const dict = await getDictionary(lang);
  const copy = dict.settingsPage;
  const memberVerificationTitle = dict.featureInfo.memberVerification.title;

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={copy.guildConfigurationTitle}
        description={copy.guildConfigurationDescription}
        actions={
          <Button asChild variant="secondary">
            <Link href={`/${lang}/community/onboarding`}>
              {memberVerificationTitle}
            </Link>
          </Button>
        }
      />

      <VerificationSettingsForm />
    </div>
  );
}

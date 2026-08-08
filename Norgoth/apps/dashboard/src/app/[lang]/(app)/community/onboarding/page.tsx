import Link from "next/link";
import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { VerificationLogsPanel } from "@/components/verification/verification-logs-panel";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function OnboardingPage({
  params,
}: PageProps<"/[lang]/community/onboarding">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
        <PageHeader
          title="Member Verification"
          description="Verification outcomes for members joining this server."
          actions={
            <Button asChild variant="secondary">
              <Link href={`/${lang}/settings/guild-configuration`}>
                Verification Settings
              </Link>
            </Button>
          }
        />

        <VerificationLogsPanel />
      </div>
  );
}

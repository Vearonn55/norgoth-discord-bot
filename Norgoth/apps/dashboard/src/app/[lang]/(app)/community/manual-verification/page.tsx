import { notFound } from "next/navigation";
import { cilTask } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { Icon } from "@/components/ui/icon";
import { ManualVerificationPanel } from "@/components/verification/manual-verification-panel";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function ManualVerificationPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title="Manual Verification"
        icon={<Icon icon={cilTask} size="xl" />}
        category="community"
        description="Review members flagged for manual verification and approve or deny access."
        infoKey="manualVerification"
      />

      <ManualVerificationPanel />
    </div>
  );
}

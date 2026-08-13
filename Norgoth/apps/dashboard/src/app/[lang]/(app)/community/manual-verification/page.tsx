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

  const dict = await getDictionary(lang);
  const info = dict.featureInfo.manualVerification;

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={info.title}
        icon={<Icon icon={cilTask} size="xl" />}
        category="community"
        description={info.description}
        infoKey="manualVerification"
      />

      <ManualVerificationPanel />
    </div>
  );
}

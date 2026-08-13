import { notFound } from "next/navigation";
import { cilCommentBubble } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { Icon } from "@/components/ui/icon";
import { AutomationSettingsPanel } from "@/components/automation/automation-settings-panel";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function WelcomeFlowPage({
  params,
}: PageProps<"/[lang]/automation/welcome-goodbye-invite">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const info = dict.featureInfo.welcomeLeave;

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={info.title}
        icon={<Icon icon={cilCommentBubble} size="xl" />}
        category="community"
        description={info.description}
        infoKey="welcomeLeave"
      />

      <AutomationSettingsPanel section="welcome" />
    </div>
  );
}

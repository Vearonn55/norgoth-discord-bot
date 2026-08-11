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

  await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
        <PageHeader
          title="Welcome & Leave"
          icon={<Icon icon={cilCommentBubble} size="xl" />}
          category="community"
          description="Send a welcome message when a member joins and a leave message when they leave, with live delivery status and a test send."
          infoKey="welcomeLeave"
        />

        <AutomationSettingsPanel section="welcome" />
      </div>
  );
}

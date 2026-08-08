import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
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
          title="Welcome & Leave Messages"
          description="Send a welcome message when a member joins and a leave message when they leave, with live delivery status and a test send."
        />

        <AutomationSettingsPanel section="welcome" />
      </div>
  );
}

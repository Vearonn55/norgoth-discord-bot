import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { AutomationSettingsPanel } from "@/components/automation/automation-settings-panel";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function AutoRolePage({
  params,
}: PageProps<"/[lang]/automation/auto-role">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
        <PageHeader
          title="Auto Role"
          description="Automatically grant a role to every member who joins the server."
        />

        <AutomationSettingsPanel section="autorole" />
      </div>
  );
}

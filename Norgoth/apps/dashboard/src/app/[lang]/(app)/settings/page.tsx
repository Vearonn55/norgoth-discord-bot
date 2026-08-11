import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { ModuleTogglesPanel } from "@/components/settings/module-toggles-panel";
import { getDictionary, hasLocale } from "../../dictionaries";

export default async function SettingsPage({
  params,
}: PageProps<"/[lang]/settings">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title="Settings"
        description="Configuration for the bot, verification, automation, and the dashboard."
      />

      <ModuleTogglesPanel />
    </div>
  );
}

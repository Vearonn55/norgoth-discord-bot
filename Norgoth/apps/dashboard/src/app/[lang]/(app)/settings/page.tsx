import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { ModuleTogglesPanel } from "@/components/settings/module-toggles-panel";
import { getDictionary, hasLocale } from "../../dictionaries";

export default async function SettingsPage({
  params,
}: PageProps<"/[lang]/settings">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={dict.settingsPage.title}
        description={dict.settingsPage.description}
      />

      <ModuleTogglesPanel />
    </div>
  );
}

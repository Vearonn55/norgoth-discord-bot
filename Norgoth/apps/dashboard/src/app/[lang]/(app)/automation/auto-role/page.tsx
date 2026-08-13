import { notFound } from "next/navigation";
import { cilUserFollow } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { Icon } from "@/components/ui/icon";
import { AutomationSettingsPanel } from "@/components/automation/automation-settings-panel";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function AutoRolePage({
  params,
}: PageProps<"/[lang]/automation/auto-role">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const info = dict.featureInfo.autoRole;

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={info.title}
        icon={<Icon icon={cilUserFollow} size="xl" />}
        category="roles"
        description={info.description}
        infoKey="autoRole"
      />

      <AutomationSettingsPanel section="autorole" />
    </div>
  );
}

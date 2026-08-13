import { notFound } from "next/navigation";
import { cilList } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { Icon } from "@/components/ui/icon";
import { AutoResponsesPanel } from "@/components/automation/auto-responses-panel";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function AutoResponsesPage({
  params,
}: PageProps<"/[lang]/automation/auto-responses">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const info = dict.featureInfo.autoResponses;

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={info.title}
        icon={<Icon icon={cilList} size="xl" />}
        category="community"
        description={info.description}
        infoKey="autoResponses"
      />

      <AutoResponsesPanel />
    </div>
  );
}

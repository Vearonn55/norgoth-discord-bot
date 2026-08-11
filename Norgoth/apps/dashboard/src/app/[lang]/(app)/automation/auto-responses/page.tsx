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

  await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
        <PageHeader
          title="Auto-Responses"
          icon={<Icon icon={cilList} size="xl" />}
          category="community"
          description="Keyword-triggered replies with match modes, optional channel restrictions, and per-rule cooldowns."
          infoKey="autoResponses"
        />

        <AutoResponsesPanel />
      </div>
  );
}

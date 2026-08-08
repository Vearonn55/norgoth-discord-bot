import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
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
          description="Keyword-triggered replies with match modes, optional channel restrictions, and per-rule cooldowns."
        />

        <AutoResponsesPanel />
      </div>
  );
}

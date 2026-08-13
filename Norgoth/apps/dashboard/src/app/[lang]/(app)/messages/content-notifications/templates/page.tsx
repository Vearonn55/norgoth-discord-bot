import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { TemplatesPanel } from "@/components/content-notifications/templates-panel";
import { getDictionary, hasLocale } from "../../../../dictionaries";

export default async function TemplatesPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  const copy = dict.contentNotifications;

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={copy.templatesPageTitle}
        description={copy.templatesPageDescription}
        category="messages"
      />
      <TemplatesPanel />
    </div>
  );
}

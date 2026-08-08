import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { TemplatesPanel } from "@/components/content-notifications/templates-panel";
import { hasLocale } from "../../../../dictionaries";

export default async function TemplatesPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title="Notification Templates"
        description="Reusable message templates with runtime content tags."
        category="messages"
      />
      <TemplatesPanel />
    </div>
  );
}

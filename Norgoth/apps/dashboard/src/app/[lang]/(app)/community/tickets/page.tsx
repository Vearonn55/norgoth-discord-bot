import { notFound } from "next/navigation";
import { cilEnvelopeClosed } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { TicketsPanel } from "@/components/community/tickets-panel";
import { Icon } from "@/components/ui/icon";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function TicketsPage({
  params,
}: PageProps<"/[lang]/community/tickets">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title="Support Tickets"
        icon={<Icon icon={cilEnvelopeClosed} size="xl" />}
        description="Private support channels opened from a panel button, with transcripts saved when tickets are closed."
      />

      <TicketsPanel />
    </div>
  );
}

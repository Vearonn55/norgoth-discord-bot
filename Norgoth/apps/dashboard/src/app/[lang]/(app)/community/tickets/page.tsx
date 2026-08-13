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

  const dict = await getDictionary(lang);
  const info = dict.featureInfo.tickets;

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={info.title}
        icon={<Icon icon={cilEnvelopeClosed} size="xl" />}
        category="support"
        description={info.description}
        infoKey="tickets"
      />

      <TicketsPanel />
    </div>
  );
}

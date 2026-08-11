import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { CampaignWizard } from "@/components/campaigns/campaign-wizard";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function NewCampaignPage({
  params,
}: PageProps<"/[lang]/campaigns/new">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
        <PageHeader
          title={dict.campaignWizard.newCampaignTitle}
          description="Create a Discord campaign: pick a channel broadcast or member DMs, write the message with rich formatting, validate the audience, and launch now or on a schedule."
        />

        <CampaignWizard lang={lang} dict={dict} />
      </div>
  );
}

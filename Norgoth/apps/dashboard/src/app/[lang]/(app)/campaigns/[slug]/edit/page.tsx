import { notFound } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { CampaignEditLoader } from "@/components/campaigns/campaign-edit-loader";
import { getDictionary, hasLocale } from "../../../../dictionaries";

export default async function EditCampaignPage({
  params,
}: PageProps<"/[lang]/campaigns/[slug]/edit">) {
  const { lang, slug } = await params;

  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
        <PageHeader
          title="Edit Campaign"
          description="Update the campaign name, delivery target, message, and schedule. Queued or running campaigns must be stopped before editing."
        />

        <CampaignEditLoader lang={lang} dict={dict} campaignId={slug} />
      </div>
  );
}

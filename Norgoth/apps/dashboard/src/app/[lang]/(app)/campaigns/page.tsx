import Link from "next/link";
import { notFound } from "next/navigation";
import { cilPlus, cilSend } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { DashboardAutoRefresh } from "@/components/dashboard/dashboard-auto-refresh";
import { CampaignCommandCenter } from "@/components/dashboard/campaign-command-center";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { getDictionary, hasLocale } from "../../dictionaries";

export default async function CampaignsPage({
  params,
}: PageProps<"/[lang]/campaigns">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);

  return (
    <>
      <DashboardAutoRefresh />

      <div className="d-flex flex-column gap-4">
        <PageHeader
          title={dict.campaignsPage.title}
          icon={<Icon icon={cilSend} size="xl" />}
          description={dict.campaignsPage.description}
          infoKey="campaigns"
          actions={
            <>
              <Button variant="secondary" asChild>
                <Link href={`/${lang}/campaigns/history`}>
                  {dict.campaignsPage.history}
                </Link>
              </Button>
              <Button variant="primary" asChild>
                <Link href={`/${lang}/campaigns/new`}>
                  <span className="d-inline-flex align-items-center gap-2">
                    <Icon icon={cilPlus} />
                    {dict.campaignsPage.createCampaign}
                  </span>
                </Link>
              </Button>
            </>
          }
        />

        <CampaignCommandCenter />
      </div>
    </>
  );
}

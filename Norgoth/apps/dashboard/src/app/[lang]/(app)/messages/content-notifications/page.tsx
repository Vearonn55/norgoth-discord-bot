import { Suspense } from "react";
import { notFound } from "next/navigation";
import { cilBell } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { Icon } from "@/components/ui/icon";
import { AccountsPanel } from "@/components/content-notifications/accounts-panel";
import { ContentNotificationsHeaderActions } from "@/components/content-notifications/header-actions";
import { ContentNotificationsModals } from "@/components/content-notifications/inventory-modals";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function ContentNotificationsPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang);
  const copy = dict.contentNotifications;
  const info = dict.featureInfo.contentNotifications;

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={info?.title ?? copy.pageTitle}
        icon={<Icon icon={cilBell} size="xl" />}
        description={info?.description ?? copy.pageDescription}
        category="messages"
        infoKey="contentNotifications"
        actions={
          <Suspense>
            <ContentNotificationsHeaderActions />
          </Suspense>
        }
      />
      <Suspense>
        <AccountsPanel />
      </Suspense>
      <Suspense>
        <ContentNotificationsModals />
      </Suspense>
    </div>
  );
}

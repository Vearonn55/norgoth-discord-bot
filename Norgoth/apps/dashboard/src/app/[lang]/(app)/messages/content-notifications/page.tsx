import { notFound } from "next/navigation";
import Link from "next/link";
import { cilBell } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { Icon } from "@/components/ui/icon";
import { AccountsPanel } from "@/components/content-notifications/accounts-panel";
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
          <div className="d-flex gap-2 flex-wrap">
            <Link
              className="btn btn-sm btn-outline-light"
              href={`/${lang}/messages/content-notifications/templates`}
            >
              {copy.navTemplates}
            </Link>
            <Link
              className="btn btn-sm btn-outline-light"
              href={`/${lang}/messages/content-notifications/sender-styles`}
            >
              {copy.navSenderStyles}
            </Link>
            <Link
              className="btn btn-sm btn-outline-light"
              href={`/${lang}/messages/content-notifications/history`}
            >
              {copy.navHistory}
            </Link>
            <Link
              className="btn btn-sm btn-outline-light"
              href={`/${lang}/messages/content-notifications/analytics`}
            >
              {copy.navAnalytics}
            </Link>
          </div>
        }
      />
      <AccountsPanel />
    </div>
  );
}

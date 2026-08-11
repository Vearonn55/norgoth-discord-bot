import { notFound } from "next/navigation";
import Link from "next/link";
import { cilBell } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { Icon } from "@/components/ui/icon";
import { AccountsPanel } from "@/components/content-notifications/accounts-panel";
import { hasLocale } from "../../../dictionaries";

export default async function ContentNotificationsPage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title="Content Notifications"
        icon={<Icon icon={cilBell} size="xl" />}
        description="Monitor YouTube, Twitch, Kick, X, and TikTok creators and publish alerts into Discord with managed webhooks."
        category="messages"
        infoKey="contentNotifications"
        actions={
          <div className="d-flex gap-2 flex-wrap">
            <Link
              className="btn btn-sm btn-outline-light"
              href={`/${lang}/messages/content-notifications/templates`}
            >
              Templates
            </Link>
            <Link
              className="btn btn-sm btn-outline-light"
              href={`/${lang}/messages/content-notifications/sender-styles`}
            >
              Sender Styles
            </Link>
            <Link
              className="btn btn-sm btn-outline-light"
              href={`/${lang}/messages/content-notifications/history`}
            >
              History
            </Link>
            <Link
              className="btn btn-sm btn-outline-light"
              href={`/${lang}/messages/content-notifications/analytics`}
            >
              Analytics
            </Link>
          </div>
        }
      />
      <AccountsPanel />
    </div>
  );
}

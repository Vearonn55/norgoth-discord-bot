import { notFound } from "next/navigation";
import { cilLink } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { InvitesPanel } from "@/components/community/invites-panel";
import { Icon } from "@/components/ui/icon";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function InvitesPage({
  params,
}: PageProps<"/[lang]/community/invites">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title="Invite Tracking"
        icon={<Icon icon={cilLink} size="xl" />}
        description="Who invited whom: join attribution, inviter leaderboard, and leave/rejoin tracking."
      />

      <InvitesPanel />
    </div>
  );
}

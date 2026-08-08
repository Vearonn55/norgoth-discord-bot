import { notFound } from "next/navigation";
import { cilStar } from "@coreui/icons";
import { PageHeader } from "@/components/layout/page-header";
import { LevelingPanel } from "@/components/community/leveling-panel";
import { Icon } from "@/components/ui/icon";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function LevelingPage({
  params,
}: PageProps<"/[lang]/community/leveling">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title="Levels & Activity"
        icon={<Icon icon={cilStar} size="xl" />}
        description="Message-based XP with level progression, level-up announcements, and role rewards."
      />

      <LevelingPanel />
    </div>
  );
}

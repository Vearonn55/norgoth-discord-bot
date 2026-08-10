import { Suspense } from "react";
import { notFound } from "next/navigation";
import { LeaderboardPanel } from "@/components/community/leaderboard-panel";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function LeaderboardPage({
  params,
}: PageProps<"/[lang]/community/leaderboard">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return (
    <Suspense fallback={null}>
      <div className="d-flex flex-column gap-4">
        <LeaderboardPanel />
      </div>
    </Suspense>
  );
}

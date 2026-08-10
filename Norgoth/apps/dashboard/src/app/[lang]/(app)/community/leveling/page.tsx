import { notFound } from "next/navigation";
import { LevelingPanel } from "@/components/community/leveling-panel";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function LevelingPage({
  params,
}: PageProps<"/[lang]/community/leveling">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
      <LevelingPanel />
    </div>
  );
}

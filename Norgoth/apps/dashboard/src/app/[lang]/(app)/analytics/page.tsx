import { notFound } from "next/navigation";
import { AnalyticsDashboard } from "@/components/dashboard/analytics-dashboard";
import { getDictionary, hasLocale } from "../../dictionaries";

export default async function AnalyticsPage({
  params,
}: PageProps<"/[lang]/analytics">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  // Keep dictionary load for locale validation / future copy wiring.
  await getDictionary(lang);

  return <AnalyticsDashboard lang={lang} />;
}

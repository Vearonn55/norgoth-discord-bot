import { Suspense } from "react";
import { notFound } from "next/navigation";
import { AuditLogsPanel } from "@/components/security/audit-logs-panel";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function AuditLogsRoute({
  params,
}: PageProps<"/[lang]/audit/logs">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return (
    <Suspense fallback={null}>
      <AuditLogsPanel />
    </Suspense>
  );
}

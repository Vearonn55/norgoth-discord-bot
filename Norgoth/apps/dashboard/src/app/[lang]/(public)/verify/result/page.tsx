import { notFound } from "next/navigation";
import { hasLocale } from "../../../dictionaries";
import { getDictionary } from "../../../dictionaries";
import type { Locale } from "@/i18n/config";
import { formatDict } from "@/lib/locale-format";

const OUTCOME_TITLES: Record<string, "titleGranted" | "titlePending" | "titleDenied" | "titleError"> =
  {
    granted: "titleGranted",
    pending: "titlePending",
    denied: "titleDenied",
    error: "titleError",
  };

export default async function VerifyResultPage({
  params,
  searchParams,
}: {
  params: Promise<{ lang: string }>;
  searchParams: Promise<{
    outcome?: string;
    reason?: string;
    cid?: string;
    code?: string;
    state?: string;
  }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const query = await searchParams;
  const dict = await getDictionary(lang as Locale);
  const copy = dict.verifyResultPage;
  const outcome = (query.outcome || "error").toLowerCase();
  const reason = (query.reason || "").toLowerCase();
  const titleKey = OUTCOME_TITLES[outcome] ?? "titleError";
  const reasonCopy =
    (copy as Record<string, string>)[reason] ||
    (outcome === "granted"
      ? copy.granted
      : outcome === "pending"
        ? copy.pending
        : outcome === "denied"
          ? copy.denied
          : copy.internal_error);

  return (
    <main className="container py-5" style={{ maxWidth: 560 }}>
      <h1 className="h3 mb-3">{copy[titleKey]}</h1>
      <p className="text-body-secondary">{reasonCopy}</p>
      {query.cid ? (
        <p className="small text-body-tertiary mb-0">
          {formatDict(copy.reference, { cid: query.cid })}
        </p>
      ) : null}
    </main>
  );
}

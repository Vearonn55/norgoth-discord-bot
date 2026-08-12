import type { ReactNode } from "react";
import type { Locale } from "@/i18n/config";
import { getDictionary, hasLocale } from "../dictionaries";
import { notFound } from "next/navigation";

export default async function PublicLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  // Prefetch dict so child pages can use it; public shell has no AppShell.
  await getDictionary(lang as Locale);

  return (
    <div className="norgoth-public min-vh-100 d-flex flex-column" lang={lang}>
      {children}
    </div>
  );
}

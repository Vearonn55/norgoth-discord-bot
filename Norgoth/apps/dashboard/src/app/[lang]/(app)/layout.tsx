import { StoreBootstrap } from "@/components/providers/store-bootstrap";
import DashboardPreferencesBridge from "@/components/layout/dashboard-preferences-bridge";
import { AppShell } from "@/components/layout/app-shell";
import { getDictionary, hasLocale } from "../dictionaries";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import type { Locale } from "@/i18n/config";

export default async function AppLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang as Locale);

  return (
    <StoreBootstrap>
      <DashboardPreferencesBridge />
      <AppShell lang={lang as Locale} dict={dict}>
        {children}
      </AppShell>
    </StoreBootstrap>
  );
}

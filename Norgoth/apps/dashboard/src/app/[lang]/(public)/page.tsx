import type { Metadata } from "next";
import { Suspense } from "react";
import { LandingPage } from "@/components/landing/landing-page";
import { getDictionary, hasLocale } from "../dictionaries";
import { notFound } from "next/navigation";
import type { Locale } from "@/i18n/config";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang as Locale);
  return {
    title: dict.landing.metaTitle,
    description: dict.landing.metaDescription,
  };
}

export default async function PublicHomePage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  const dict = await getDictionary(lang as Locale);
  return (
    <Suspense fallback={null}>
      <LandingPage copy={dict.landing} lang={lang} />
    </Suspense>
  );
}

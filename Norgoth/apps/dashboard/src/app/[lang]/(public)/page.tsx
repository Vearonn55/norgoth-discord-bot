import { Suspense } from "react";
import { LandingPage } from "@/components/landing/landing-page";
import { hasLocale } from "../dictionaries";
import { notFound } from "next/navigation";

export default async function PublicHomePage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  return (
    <Suspense fallback={null}>
      <LandingPage />
    </Suspense>
  );
}

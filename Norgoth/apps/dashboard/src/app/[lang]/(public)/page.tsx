import type { Metadata } from "next";
import { LandingPage } from "@/components/landing/landing-page";
import { getDictionary, hasLocale } from "../dictionaries";
import { notFound } from "next/navigation";
import type { Locale } from "@/i18n/config";
import { getDashboardOrigin } from "@/lib/dashboard-origin";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};
  const dict = await getDictionary(lang as Locale);
  const origin = getDashboardOrigin();
  const title = dict.landing.metaTitle;
  const description = dict.landing.metaDescription;
  const canonical = `/${lang}`;

  return {
    metadataBase: new URL(origin),
    title,
    description,
    alternates: {
      canonical,
      languages: { en: "/en", tr: "/tr" },
    },
    openGraph: {
      title,
      description,
      url: canonical,
      siteName: "NorBot",
      locale: lang === "tr" ? "tr_TR" : "en_US",
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
    },
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
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "NorBot",
    applicationCategory: "BusinessApplication",
    offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <LandingPage copy={dict.landing} sidebar={dict.sidebar} lang={lang} />
    </>
  );
}

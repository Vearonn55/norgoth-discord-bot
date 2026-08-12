import { hasLocale } from "./dictionaries";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

/** Lang-level layout: locale gate only. Shells live in route groups. */
export default async function LangLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();
  return (
    <>
      <script
        dangerouslySetInnerHTML={{
          __html: `document.documentElement.lang=${JSON.stringify(lang)};`,
        }}
      />
      {children}
    </>
  );
}

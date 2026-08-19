import Link from "next/link";
import type { LandingCopy } from "@/components/landing/landing-copy";

export function LandingFooter({
  lang,
  copy,
}: {
  lang: string;
  copy: LandingCopy;
}) {
  return (
    <footer className="border-top border-secondary-subtle py-4 mt-auto">
      <div
        className="container d-flex flex-wrap justify-content-between gap-2 small text-body-secondary"
        style={{ maxWidth: 1100 }}
      >
        <span>{copy.footerProduct}</span>
        <span>{copy.footerTagline}</span>
        <span className="d-flex gap-3">
          <Link
            href="/en"
            className="text-decoration-none text-body-secondary"
            aria-current={lang === "en" ? "page" : undefined}
          >
            {copy.langEn}
          </Link>
          <Link
            href="/tr"
            className="text-decoration-none text-body-secondary"
            aria-current={lang === "tr" ? "page" : undefined}
          >
            {copy.langTr}
          </Link>
        </span>
      </div>
    </footer>
  );
}

import Link from "next/link";
import { notFound } from "next/navigation";
import { CCol, CRow } from "@/components/ui/coreui";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getDictionary, hasLocale } from "../../../dictionaries";

export default async function LanguageSettingsPage({
  params,
}: PageProps<"/[lang]/settings/language">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const copy = dict.settingsPage;
  const locales = [
    { code: "en", name: copy.english },
    { code: "tr", name: copy.turkish },
  ];

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={copy.languagePageTitle}
        description={copy.languagePageDescription}
        actions={
          <Button asChild variant="secondary">
            <Link href={`/${lang}/settings`}>{copy.backToSettings}</Link>
          </Button>
        }
      />

      <Card>
        <div className="d-flex flex-column gap-4">
          <div>
            <h2 className="h5 mb-0 fw-semibold">{copy.availableLanguages}</h2>
            <p className="mt-1 mb-0 small text-body-secondary">
              {copy.availableLanguagesHelp}
            </p>
          </div>

          <CRow className="g-3">
            {locales.map((locale) => {
              const isActive = locale.code === lang;

              return (
                <CCol key={locale.code} md={6}>
                  <div className="border rounded p-4 h-100">
                    <div className="d-flex align-items-center justify-content-between gap-3">
                      <div>
                        <div className="fw-semibold">{locale.name}</div>
                        <div className="mt-1 small text-body-secondary">
                          {copy.routeLabel.replace("{code}", locale.code)}
                        </div>
                      </div>

                      {isActive ? (
                        <Badge variant="success">{copy.active}</Badge>
                      ) : (
                        <Button asChild variant="primary">
                          <Link href={`/${locale.code}/settings/language`}>
                            {copy.switch}
                          </Link>
                        </Button>
                      )}
                    </div>
                  </div>
                </CCol>
              );
            })}
          </CRow>
        </div>
      </Card>
    </div>
  );
}

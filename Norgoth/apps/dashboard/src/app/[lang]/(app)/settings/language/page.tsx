import Link from "next/link";
import { notFound } from "next/navigation";
import { CCol, CRow } from "@/components/ui/coreui";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getDictionary, hasLocale } from "../../../dictionaries";

const LOCALES = [
  { code: "en", name: "English" },
  { code: "tr", name: "Türkçe" },
];

export default async function LanguageSettingsPage({
  params,
}: PageProps<"/[lang]/settings/language">) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  await getDictionary(lang);

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title="Language & Localization"
        description="Switch the dashboard language. The selected locale is part of the URL, so links can be shared per language."
        actions={
          <Button asChild variant="secondary">
            <Link href={`/${lang}/settings`}>Back to Settings</Link>
          </Button>
        }
      />

      <Card>
        <div className="d-flex flex-column gap-4">
          <div>
            <h2 className="h5 mb-0 fw-semibold">Available Languages</h2>
            <p className="mt-1 mb-0 small text-body-secondary">
              The dashboard ships with English and Turkish dictionaries.
            </p>
          </div>

          <CRow className="g-3">
            {LOCALES.map((locale) => {
              const isActive = locale.code === lang;

              return (
                <CCol key={locale.code} md={6}>
                  <div className="border rounded p-4 h-100">
                    <div className="d-flex align-items-center justify-content-between gap-3">
                      <div>
                        <div className="fw-semibold">{locale.name}</div>
                        <div className="mt-1 small text-body-secondary">
                          Route: /{locale.code}
                        </div>
                      </div>

                      {isActive ? (
                        <Badge variant="success">Active</Badge>
                      ) : (
                        <Button asChild variant="primary">
                          <Link href={`/${locale.code}/settings/language`}>
                            Switch
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

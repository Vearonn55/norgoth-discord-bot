"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { cilArrowLeft, cilTask } from "@coreui/icons";
import { CAlert, CSpinner } from "@coreui/react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { ReviewRecord } from "@/components/verification/review-transcript";
import { useManualReviewStore } from "@/stores/manual-review-store";
import { useLocaleDict } from "@/lib/locale-dict";

/**
 * Read-only transcript of a single review record, reachable via the deep link
 * embedded in the verification log channel. The `?g=` query names the guild;
 * authorization is enforced server-side by the detail endpoint (a 403 renders a
 * clear message rather than the record).
 */
export default function ReviewTranscriptPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const dict = useLocaleDict();
  const v = dict.verificationPage;
  const lang = String(params?.lang || "en");
  const reviewId = String(params?.reviewId || "");
  const guildId = searchParams.get("g") ?? "";

  const detail = useManualReviewStore((s) => s.detail);
  const detailLoading = useManualReviewStore((s) => s.detailLoading);
  const detailError = useManualReviewStore((s) => s.detailError);
  const loadDetail = useManualReviewStore((s) => s.loadDetail);

  useEffect(() => {
    if (guildId && reviewId) {
      void loadDetail(guildId, reviewId);
    }
  }, [guildId, reviewId, loadDetail]);

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={v.reviewRecordTitle}
        icon={<Icon icon={cilTask} size="xl" />}
        category="community"
        description={v.reviewRecordDescription}
        actions={
          <Link
            href={`/${lang}/community/manual-verification`}
            className="btn btn-secondary btn-sm d-inline-flex align-items-center gap-2"
          >
            <Icon icon={cilArrowLeft} height={14} />
            {v.backToQueue}
          </Link>
        }
      />

      <Card>
        {!guildId ? (
          <CAlert color="warning" className="mb-0">
            {v.missingGuildLink}
          </CAlert>
        ) : detailLoading ? (
          <div className="d-flex align-items-center gap-2 text-body-secondary">
            <CSpinner size="sm" />
            {dict.common.loading}
          </div>
        ) : detailError ? (
          <CAlert color="warning" className="mb-0">
            {detailError}
          </CAlert>
        ) : detail ? (
          <ReviewRecord detail={detail} lang={lang} />
        ) : null}
      </Card>
    </div>
  );
}

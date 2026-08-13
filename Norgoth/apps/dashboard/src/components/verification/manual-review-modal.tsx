"use client";

import { useEffect } from "react";
import { CAlert, CSpinner } from "@coreui/react";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { Button } from "@/components/ui/button";
import { ReviewRecord } from "@/components/verification/review-transcript";
import { useManualReviewStore } from "@/stores/manual-review-store";
import { useLocaleDict } from "@/lib/locale-dict";

type ManualReviewModalProps = {
  visible: boolean;
  guildId: string;
  attemptId: string | null;
  lang: string;
  onClose: () => void;
  onReviewed: () => void;
};

/**
 * Popout that shows the full risk analysis + explicit trigger for one pending
 * member and offers Approve / Deny. Loads the read-only transcript detail on
 * open; on a successful decision it notifies the parent to refresh the queue.
 */
export function ManualReviewModal({
  visible,
  guildId,
  attemptId,
  lang,
  onClose,
  onReviewed,
}: ManualReviewModalProps) {
  const dict = useLocaleDict();
  const d = dict.verificationPage;
  const detail = useManualReviewStore((s) => s.detail);
  const detailLoading = useManualReviewStore((s) => s.detailLoading);
  const detailError = useManualReviewStore((s) => s.detailError);
  const loadDetail = useManualReviewStore((s) => s.loadDetail);
  const review = useManualReviewStore((s) => s.review);
  const reviewingId = useManualReviewStore((s) => s.reviewingId);
  const reviewError = useManualReviewStore((s) => s.reviewError);

  useEffect(() => {
    if (visible && attemptId) {
      void loadDetail(guildId, attemptId);
    }
  }, [visible, attemptId, guildId, loadDetail]);

  async function handleDecision(approved: boolean) {
    if (!attemptId) return;
    const result = await review(guildId, attemptId, approved);
    if (result.ok) {
      onReviewed();
      onClose();
    }
  }

  const pending = detail?.status === "manual_review";
  const busy = reviewingId !== null;

  return (
    <FeatureConfigurationModal
      visible={visible}
      onClose={onClose}
      title={d.reviewTitle}
      description={d.reviewDesc}
      category="community"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            {d.close}
          </Button>
          {pending ? (
            <>
              <Button
                variant="danger"
                onClick={() => void handleDecision(false)}
                disabled={busy}
              >
                {busy ? "…" : d.deny}
              </Button>
              <Button
                variant="primary"
                onClick={() => void handleDecision(true)}
                disabled={busy}
              >
                {busy ? "…" : d.approve}
              </Button>
            </>
          ) : null}
        </>
      }
    >
      {reviewError ? (
        <CAlert color="danger" className="py-2 px-3 mb-3">
          {reviewError}
        </CAlert>
      ) : null}

      {detailLoading ? (
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          {d.loading}
        </div>
      ) : detailError ? (
        <CAlert color="warning" className="mb-0">
          {detailError}
        </CAlert>
      ) : detail ? (
        <ReviewRecord detail={detail} lang={lang} />
      ) : null}
    </FeatureConfigurationModal>
  );
}

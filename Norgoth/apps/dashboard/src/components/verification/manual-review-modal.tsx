"use client";

import { useEffect } from "react";
import { CAlert, CSpinner } from "@coreui/react";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { Button } from "@/components/ui/button";
import { ReviewRecord } from "@/components/verification/review-transcript";
import { useManualReviewStore } from "@/stores/manual-review-store";

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
      title="Review Member"
      description="Approve or deny this pending member based on the risk analysis below."
      category="community"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Close
          </Button>
          {pending ? (
            <>
              <Button
                variant="danger"
                onClick={() => void handleDecision(false)}
                disabled={busy}
              >
                {busy ? "…" : "Deny"}
              </Button>
              <Button
                variant="primary"
                onClick={() => void handleDecision(true)}
                disabled={busy}
              >
                {busy ? "…" : "Approve"}
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
          Loading…
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

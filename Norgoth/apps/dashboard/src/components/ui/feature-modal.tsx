"use client";

import { useEffect, useRef, type ReactNode } from "react";
import {
  CAlert,
  CModal,
  CModalBody,
  CModalFooter,
  CModalHeader,
  CModalTitle,
} from "@coreui/react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { NorgothCategory } from "@/lib/design/category";
import { categoryAccent } from "@/lib/design/category";
import { useLocaleDict } from "@/lib/locale-dict";
import { shouldInvokeModalClose } from "@/lib/cn-url-state";

export type FeatureModalSaveState = "idle" | "dirty" | "saving" | "saved" | "error";

type FeatureConfigurationModalProps = {
  visible: boolean;
  title: string;
  description?: string;
  category?: NorgothCategory;
  icon?: string | string[];
  children: ReactNode;
  onClose: () => void;
  /** When provided, a Save button is rendered in the footer. */
  onSave?: () => void | Promise<void>;
  saving?: boolean;
  error?: string | null;
  saveState?: FeatureModalSaveState;
  saveLabel?: string;
  savedLabel?: string;
  cancelLabel?: string;
  saveDisabled?: boolean;
  size?: "sm" | "lg" | "xl";
  /** Replaces the default footer actions entirely. */
  footer?: ReactNode;
  /** CoreUI `modal-dialog-scrollable`. Disable for split-pane sticky preview. */
  scrollable?: boolean;
  errorSummaryLabel?: string;
  dialogClassName?: string;
  bodyClassName?: string;
};

/**
 * Single reusable CoreUI modal pattern for feature configuration popouts.
 * Provides a consistent header, scrollable body, fixed footer with Save/Cancel,
 * save-state feedback and error surface. Does NOT close on failed save — the
 * parent controls `visible` and only closes on success.
 */
export function FeatureConfigurationModal({
  visible,
  title,
  description,
  category,
  icon,
  children,
  onClose,
  onSave,
  saving = false,
  error,
  saveState,
  saveLabel,
  savedLabel,
  cancelLabel,
  saveDisabled = false,
  size = "lg",
  footer,
  scrollable = true,
  dialogClassName,
  bodyClassName,
  errorSummaryLabel,
}: FeatureConfigurationModalProps) {
  const dict = useLocaleDict();
  const resolvedSave = saveLabel ?? dict.common.save;
  const resolvedSaved = savedLabel ?? dict.common.saved;
  const resolvedCancel = cancelLabel ?? dict.common.cancel;
  const accent = category ? categoryAccent(category) : undefined;
  const isSaving = saving || saveState === "saving";
  const isSaved = saveState === "saved";
  const openerRef = useRef<HTMLElement | null>(null);
  const wasVisible = useRef(false);
  const errorRef = useRef<HTMLDivElement | null>(null);
  const previousError = useRef<string | null>(null);

  useEffect(() => {
    if (visible && !wasVisible.current) {
      openerRef.current =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
    }
    if (!visible && wasVisible.current) {
      const opener = openerRef.current;
      if (opener) queueMicrotask(() => opener.focus());
    }
    wasVisible.current = visible;
  }, [visible]);

  useEffect(() => {
    if (error && error !== previousError.current && errorRef.current) {
      errorRef.current.scrollIntoView({ block: "nearest", behavior: "smooth" });
      errorRef.current.focus({ preventScroll: true });
    }
    previousError.current = error ?? null;
  }, [error]);

  function handleClose() {
    if (!shouldInvokeModalClose(visible, isSaving)) return;
    onClose();
  }

  return (
    <CModal
      visible={visible}
      onClose={handleClose}
      size={size}
      alignment="center"
      scrollable={scrollable}
      backdrop
      className={dialogClassName}
    >
      <CModalHeader style={accent ? { borderBottomColor: accent } : undefined}>
        <CModalTitle className="d-flex align-items-center gap-2">
          {icon ? (
            <Icon
              icon={icon}
              style={accent ? { color: accent } : undefined}
              height={20}
            />
          ) : null}
          {title}
        </CModalTitle>
      </CModalHeader>
      <CModalBody className={bodyClassName}>
        {description ? (
          <p className="text-body-secondary small mb-3">{description}</p>
        ) : null}
        {error ? (
          <div
            ref={errorRef}
            tabIndex={-1}
            role="alert"
            aria-live="assertive"
            aria-label={errorSummaryLabel}
            className="mb-3"
          >
            <CAlert color="danger" className="py-2 px-3 mb-0">
              {error}
            </CAlert>
          </div>
        ) : null}
        {children}
      </CModalBody>
      <CModalFooter>
        {footer ?? (
          <>
            <Button variant="secondary" onClick={handleClose} disabled={isSaving}>
              {resolvedCancel}
            </Button>
            {onSave ? (
              <Button
                variant="primary"
                onClick={() => void onSave()}
                disabled={isSaving || saveDisabled}
              >
                {isSaving
                  ? dict.common.saving
                  : isSaved
                    ? resolvedSaved
                    : resolvedSave}
              </Button>
            ) : null}
          </>
        )}
      </CModalFooter>
    </CModal>
  );
}

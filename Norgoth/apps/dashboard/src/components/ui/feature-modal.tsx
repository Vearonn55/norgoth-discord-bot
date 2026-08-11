"use client";

import type { ReactNode } from "react";
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
  saveLabel = "Save",
  savedLabel = "Saved",
  cancelLabel = "Cancel",
  saveDisabled = false,
  size = "lg",
  footer,
}: FeatureConfigurationModalProps) {
  const accent = category ? categoryAccent(category) : undefined;
  const isSaving = saving || saveState === "saving";
  const isSaved = saveState === "saved";

  return (
    <CModal
      visible={visible}
      onClose={onClose}
      size={size}
      alignment="center"
      scrollable
      backdrop
    >
      <CModalHeader style={accent ? { borderBottomColor: accent } : undefined}>
        <CModalTitle className="d-flex align-items-center gap-2">
          {icon ? (
            <Icon icon={icon} style={accent ? { color: accent } : undefined} height={20} />
          ) : null}
          {title}
        </CModalTitle>
      </CModalHeader>
      <CModalBody>
        {description ? (
          <p className="text-body-secondary small mb-3">{description}</p>
        ) : null}
        {error ? (
          <CAlert color="danger" className="py-2 px-3 mb-3">
            {error}
          </CAlert>
        ) : null}
        {children}
      </CModalBody>
      <CModalFooter>
        {footer ?? (
          <>
            <Button variant="secondary" onClick={onClose} disabled={isSaving}>
              {cancelLabel}
            </Button>
            {onSave ? (
              <Button
                variant="primary"
                onClick={() => void onSave()}
                disabled={isSaving || saveDisabled}
              >
                {isSaving ? "Saving…" : isSaved ? savedLabel : saveLabel}
              </Button>
            ) : null}
          </>
        )}
      </CModalFooter>
    </CModal>
  );
}

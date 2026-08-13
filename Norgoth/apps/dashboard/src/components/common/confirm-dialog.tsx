"use client";

import {
  CModal,
  CModalBody,
  CModalFooter,
  CModalHeader,
  CModalTitle,
} from "@coreui/react";
import { Button } from "@/components/ui/button";
import { useLocaleDict } from "@/lib/locale-dict";

type ConfirmDialogProps = {
  visible: boolean;
  title: string;
  message: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

/**
 * Shared confirmation modal built on CoreUI's CModal. Use for destructive
 * actions instead of window.confirm.
 */
export function ConfirmDialog({
  visible,
  title,
  message,
  confirmLabel,
  cancelLabel,
  destructive = false,
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const dict = useLocaleDict();
  const resolvedConfirm = confirmLabel ?? dict.common.confirm;
  const resolvedCancel = cancelLabel ?? dict.common.cancel;

  return (
    <CModal visible={visible} onClose={onCancel} alignment="center">
      <CModalHeader>
        <CModalTitle>{title}</CModalTitle>
      </CModalHeader>
      <CModalBody>
        {typeof message === "string" ? (
          <p className="mb-0 text-body-secondary">{message}</p>
        ) : (
          message
        )}
      </CModalBody>
      <CModalFooter>
        <Button variant="secondary" onClick={onCancel} disabled={busy}>
          {resolvedCancel}
        </Button>
        <Button
          variant={destructive ? "danger" : "primary"}
          onClick={onConfirm}
          disabled={busy}
        >
          {busy ? dict.common.working : resolvedConfirm}
        </Button>
      </CModalFooter>
    </CModal>
  );
}

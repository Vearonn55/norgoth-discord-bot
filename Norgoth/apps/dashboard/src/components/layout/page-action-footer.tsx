import type { ReactNode } from "react";

type PageActionFooterProps = {
  children: ReactNode;
  /** Optional left-aligned status/help content (e.g. saved-at, error text). */
  status?: ReactNode;
};

/**
 * Right-aligned, page-level action area rendered in normal document flow at the
 * bottom of a page's content (not fixed/absolute, so it never overlaps or
 * overflows on narrow screens). Use for the primary "Save Settings" action.
 */
export function PageActionFooter({ children, status }: PageActionFooterProps) {
  return (
    <div className="d-flex flex-wrap align-items-center justify-content-between gap-3 pt-2 mt-2 border-top">
      <div className="d-flex align-items-center gap-3 min-w-0">{status}</div>
      <div className="d-flex flex-wrap align-items-center gap-2 justify-content-end ms-auto">
        {children}
      </div>
    </div>
  );
}

/**
 * Viewport-aware popover placement. Prefers bottom-start, flips above the
 * trigger when there is not enough space below, and shifts horizontally so the
 * panel stays inside the viewport. Pure and DOM-free for unit tests.
 */

export type PlaceRect = {
  top: number;
  left: number;
  width: number;
  height: number;
  bottom?: number;
  right?: number;
};

export type PlaceSize = {
  width: number;
  height: number;
};

export type PlaceViewport = {
  width: number;
  height: number;
};

export type PlacePopoverResult = {
  top: number;
  left: number;
  placement: "bottom-start" | "top-start";
};

const VIEWPORT_PADDING = 8;

export function placePopover(
  triggerRect: PlaceRect,
  popoverSize: PlaceSize,
  viewport: PlaceViewport,
  gap = 4,
): PlacePopoverResult {
  const triggerBottom = triggerRect.bottom ?? triggerRect.top + triggerRect.height;
  const spaceBelow = viewport.height - triggerBottom - VIEWPORT_PADDING;
  const spaceAbove = triggerRect.top - VIEWPORT_PADDING;
  const fitsBelow = spaceBelow >= popoverSize.height;
  const placement: PlacePopoverResult["placement"] =
    fitsBelow || spaceBelow >= spaceAbove ? "bottom-start" : "top-start";

  let top =
    placement === "bottom-start"
      ? triggerBottom + gap
      : triggerRect.top - popoverSize.height - gap;

  const maxTop = Math.max(
    VIEWPORT_PADDING,
    viewport.height - popoverSize.height - VIEWPORT_PADDING,
  );
  top = Math.min(Math.max(top, VIEWPORT_PADDING), maxTop);

  let left = triggerRect.left;
  const maxLeft = Math.max(
    VIEWPORT_PADDING,
    viewport.width - popoverSize.width - VIEWPORT_PADDING,
  );
  left = Math.min(Math.max(left, VIEWPORT_PADDING), maxLeft);

  return { top, left, placement };
}

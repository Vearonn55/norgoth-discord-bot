"use client";

/**
 * Format remaining milliseconds as HH:MM:SS (non-negative).
 */
export function formatCountdown(ms: number): string {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(totalSec / 3600);
  const minutes = Math.floor((totalSec % 3600) / 60);
  const seconds = totalSec % 60;
  return [hours, minutes, seconds]
    .map((part) => String(part).padStart(2, "0"))
    .join(":");
}

/**
 * Remaining ms until an ISO timestamp. Negative if past.
 * Prefer snapshotRemainingMs when remaining_seconds + receivedAt are available.
 */
export function msUntil(iso: string | null | undefined, nowMs = Date.now()): number {
  if (!iso) return 0;
  const target = Date.parse(iso);
  if (!Number.isFinite(target)) return 0;
  return target - nowMs;
}

/** Snapshot from a status/config response for skew-safe countdown ticks. */
export type CountdownSnapshot = {
  remainingSeconds: number | null;
  serverTime: string | null;
  nextRefreshAt: string | null;
  receivedAt: number;
};

/**
 * Remaining ms from a backend countdown snapshot.
 * Uses remaining_seconds at receive time minus local elapsed (skew-safe).
 * Falls back to next_refresh_at vs Date.now when remaining is unknown.
 */
export function snapshotRemainingMs(
  snapshot: CountdownSnapshot | null | undefined,
  nowMs = Date.now()
): number {
  if (!snapshot) return 0;
  if (
    snapshot.remainingSeconds != null &&
    Number.isFinite(snapshot.remainingSeconds)
  ) {
    const elapsedSec = Math.max(0, (nowMs - snapshot.receivedAt) / 1000);
    return Math.max(0, snapshot.remainingSeconds - elapsedSec) * 1000;
  }
  return Math.max(0, msUntil(snapshot.nextRefreshAt, nowMs));
}

/** Placeholder while scheduler state is unknown. */
export const COUNTDOWN_PLACEHOLDER = "--:--:--";

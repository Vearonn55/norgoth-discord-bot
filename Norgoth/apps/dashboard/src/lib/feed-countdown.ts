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
 */
export function msUntil(iso: string | null | undefined, nowMs = Date.now()): number {
  if (!iso) return 0;
  const target = Date.parse(iso);
  if (!Number.isFinite(target)) return 0;
  return target - nowMs;
}

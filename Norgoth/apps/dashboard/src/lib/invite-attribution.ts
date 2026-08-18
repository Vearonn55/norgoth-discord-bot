import type { RecentJoin } from "@/stores/invites-store";

export type InviteAttributionCopy = {
  vanityUrl: string;
  unknown: string;
  attributionDeleted: string;
  attributionAmbiguous: string;
  attributionUnavailable: string;
  attributionConsumedOneUse: string;
  invitationSourceOneUse: string;
};

export function invitedByLabel(
  row: Pick<RecentJoin, "inviter_name" | "inviter_id" | "code" | "attribution">,
  copy: InviteAttributionCopy,
): string {
  const attribution = (row.attribution || "").toLowerCase();
  if (row.inviter_name) {
    return row.inviter_name;
  }
  if (row.inviter_id) {
    return row.inviter_id;
  }
  if (attribution === "vanity" || row.code === "vanity") {
    return copy.vanityUrl;
  }
  if (attribution === "consumed_one_use") {
    return copy.attributionConsumedOneUse;
  }
  if (attribution === "deleted") {
    return copy.attributionDeleted;
  }
  if (attribution === "ambiguous") {
    return copy.attributionAmbiguous;
  }
  if (attribution === "unavailable") {
    return copy.attributionUnavailable;
  }
  return copy.unknown;
}

export function invitationSourceLabel(
  row: Pick<RecentJoin, "code" | "attribution">,
  copy: InviteAttributionCopy,
): string {
  const attribution = (row.attribution || "").toLowerCase();
  if (attribution === "consumed_one_use") {
    return row.code
      ? `${copy.invitationSourceOneUse} (${row.code})`
      : copy.invitationSourceOneUse;
  }
  if (attribution === "vanity" || row.code === "vanity") {
    return copy.vanityUrl;
  }
  return row.code && row.code !== "vanity" ? row.code : "—";
}

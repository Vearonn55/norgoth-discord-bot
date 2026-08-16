import type { RecentJoin } from "@/stores/invites-store";

export type InviteAttributionCopy = {
  vanityUrl: string;
  unknown: string;
  attributionDeleted: string;
  attributionAmbiguous: string;
  attributionUnavailable: string;
};

export function invitedByLabel(
  row: Pick<RecentJoin, "inviter_name" | "inviter_id" | "code" | "attribution">,
  copy: InviteAttributionCopy,
): string {
  const attribution = (row.attribution || "").toLowerCase();
  if (row.inviter_name) {
    return row.inviter_name;
  }
  if (attribution === "vanity" || row.code === "vanity") {
    return copy.vanityUrl;
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
  if (row.inviter_id) {
    return row.inviter_id;
  }
  return copy.unknown;
}

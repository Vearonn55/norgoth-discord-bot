/**
 * Normalized manual-review reason codes and their localized (TR/EN) labels.
 *
 * Reasons are derived from persisted boolean risk signals and, when needed,
 * the stored decision reason string on the verification attempt.
 */

export type ManualReviewReasonCode =
  | "vpn_or_proxy"
  | "shared_ip"
  | "high_risk_server"
  | "membership_check_unavailable";

type Localized = { en: string; tr: string };

const REASON_LABELS: Record<ManualReviewReasonCode, Localized> = {
  vpn_or_proxy: {
    en: "VPN / Proxy detected",
    tr: "VPN / Proxy tespit edildi",
  },
  shared_ip: {
    en: "Shared IP / possible alternate account",
    tr: "Paylaşılan IP / olası ikincil hesap",
  },
  high_risk_server: {
    en: "High Risk Server member",
    tr: "Yüksek Riskli Sunucu üyesi",
  },
  membership_check_unavailable: {
    en: "Server membership check unavailable",
    tr: "Sunucu üyeliği doğrulaması kullanılamıyor",
  },
};

const SHORT_LABELS: Record<ManualReviewReasonCode, Localized> = {
  vpn_or_proxy: { en: "VPN / Proxy", tr: "VPN / Proxy" },
  shared_ip: { en: "Shared IP", tr: "Paylaşılan IP" },
  high_risk_server: { en: "High Risk", tr: "Yüksek Risk" },
  membership_check_unavailable: {
    en: "Membership check",
    tr: "Üyelik kontrolü",
  },
};

export type ManualReviewSignals = {
  vpn_or_proxy_detected?: boolean | null;
  shared_ip_detected?: boolean | null;
  high_risk_guild_detected?: boolean | null;
  reason?: string | null;
};

/** Derive every triggered reason code from the persisted attempt signals. */
export function deriveManualReviewReasons(
  signals: ManualReviewSignals,
): ManualReviewReasonCode[] {
  const codes: ManualReviewReasonCode[] = [];
  if (signals.vpn_or_proxy_detected) codes.push("vpn_or_proxy");
  if (signals.shared_ip_detected) codes.push("shared_ip");
  if (signals.high_risk_guild_detected) codes.push("high_risk_server");
  if (signals.reason === "membership_check_unavailable") {
    codes.push("membership_check_unavailable");
  }
  return codes;
}

function pick(label: Localized, lang: string): string {
  return lang.toLowerCase().startsWith("tr") ? label.tr : label.en;
}

export function manualReviewReasonLabel(
  code: ManualReviewReasonCode,
  lang: string,
): string {
  return pick(REASON_LABELS[code], lang);
}

export function manualReviewReasonShortLabel(
  code: ManualReviewReasonCode,
  lang: string,
): string {
  return pick(SHORT_LABELS[code], lang);
}

export function manualReviewReasonHeading(lang: string): string {
  return lang.toLowerCase().startsWith("tr")
    ? "Manuel inceleme nedeni"
    : "Manual review reason";
}

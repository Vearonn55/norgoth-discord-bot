/**
 * Normalized manual-review reason codes and their localized (TR/EN) labels.
 *
 * Reasons are derived from persisted boolean risk signals and, when needed,
 * the stored decision reason string on the verification attempt.
 */

export type ManualReviewReasonCode =
  | "vpn_or_proxy"
  | "shared_ip"
  | "banned_ip_match"
  | "high_risk_server"
  | "membership_check_unavailable"
  | "risk_provider_unavailable";

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
  banned_ip_match: {
    en: "Possible ban evasion (matched banned account IP)",
    tr: "Olası ban kaçırma (yasaklı hesap IP eşleşmesi)",
  },
  high_risk_server: {
    en: "High Risk Server member",
    tr: "Yüksek Riskli Sunucu üyesi",
  },
  membership_check_unavailable: {
    en: "Server membership check unavailable",
    tr: "Sunucu üyeliği doğrulaması kullanılamıyor",
  },
  risk_provider_unavailable: {
    en: "VPN / Proxy risk check unavailable",
    tr: "VPN / Proxy risk kontrolü kullanılamıyor",
  },
};

const SHORT_LABELS: Record<ManualReviewReasonCode, Localized> = {
  vpn_or_proxy: { en: "VPN / Proxy", tr: "VPN / Proxy" },
  shared_ip: { en: "Shared IP", tr: "Paylaşılan IP" },
  banned_ip_match: { en: "Banned IP match", tr: "Yasaklı IP eşleşmesi" },
  high_risk_server: { en: "High Risk", tr: "Yüksek Risk" },
  membership_check_unavailable: {
    en: "Membership check",
    tr: "Üyelik kontrolü",
  },
  risk_provider_unavailable: {
    en: "Risk check unavailable",
    tr: "Risk kontrolü yok",
  },
};

export type ManualReviewSignals = {
  vpn_or_proxy_detected?: boolean | null;
  shared_ip_detected?: boolean | null;
  banned_ip_match_detected?: boolean | null;
  high_risk_guild_detected?: boolean | null;
  reason?: string | null;
  review_reasons?: string[] | null;
};

const ORDERED_CODES: ManualReviewReasonCode[] = [
  "vpn_or_proxy",
  "shared_ip",
  "banned_ip_match",
  "high_risk_server",
  "membership_check_unavailable",
  "risk_provider_unavailable",
];

function isReasonCode(value: string): value is ManualReviewReasonCode {
  return (ORDERED_CODES as string[]).includes(value);
}

/** Derive every triggered reason code from the persisted attempt signals. */
export function deriveManualReviewReasons(
  signals: ManualReviewSignals,
): ManualReviewReasonCode[] {
  if (signals.review_reasons?.length) {
    return signals.review_reasons.filter(isReasonCode);
  }

  const codes: ManualReviewReasonCode[] = [];
  if (signals.vpn_or_proxy_detected) codes.push("vpn_or_proxy");
  if (signals.shared_ip_detected) codes.push("shared_ip");
  if (signals.banned_ip_match_detected) codes.push("banned_ip_match");
  if (signals.high_risk_guild_detected) codes.push("high_risk_server");
  if (signals.reason === "membership_check_unavailable") {
    codes.push("membership_check_unavailable");
  }
  if (signals.reason === "risk_provider_unavailable") {
    codes.push("risk_provider_unavailable");
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
  return pick(
    { en: "Reasons", tr: "Nedenler" },
    lang,
  );
}

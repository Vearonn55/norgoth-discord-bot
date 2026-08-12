"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { cilCheckCircle } from "@coreui/icons";
import { MetricWidget } from "@/components/ui/metric-widget";
import { Icon } from "@/components/ui/icon";
import { apiUrl } from "@/lib/api";
import { useGuildStore } from "@/stores/guild-store";

type VerificationHomeState = {
  label: string;
  accent: "success" | "warning" | "danger";
  helper: string;
};

export function HomeVerificationMetric({ lang }: { lang: string }) {
  const selectedGuild = useGuildStore((s) => s.selectedGuild);
  const [state, setState] = useState<VerificationHomeState>({
    label: "Select a server",
    accent: "warning",
    helper: "Choose a server to see verification status",
  });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!selectedGuild?.id) {
        if (!cancelled) {
          setState({
            label: "Select a server",
            accent: "warning",
            helper: "Choose a server to see verification status",
          });
        }
        return;
      }

      try {
        const response = await fetch(
          apiUrl(`/api/v1/guilds/${selectedGuild.id}/configuration/setup`),
          { cache: "no-store", credentials: "include" }
        );
        if (!response.ok) {
          if (!cancelled) {
            setState({
              label: "Unavailable",
              accent: "warning",
              helper: selectedGuild.name,
            });
          }
          return;
        }
        const body = (await response.json()) as {
          setup_state?: string;
          enabled?: boolean;
        };
        const setup = body.setup_state ?? "not_configured";
        if (cancelled) return;
        if (setup === "active") {
          setState({
            label: "Enabled",
            accent: "success",
            helper: selectedGuild.name,
          });
        } else if (setup === "disabled") {
          setState({
            label: "Disabled",
            accent: "warning",
            helper: selectedGuild.name,
          });
        } else if (setup === "incomplete" || setup === "not_configured") {
          setState({
            label: "Not configured",
            accent: "warning",
            helper: selectedGuild.name,
          });
        } else {
          setState({
            label: setup,
            accent: "warning",
            helper: selectedGuild.name,
          });
        }
      } catch {
        if (!cancelled) {
          setState({
            label: "Unavailable",
            accent: "warning",
            helper: selectedGuild.name,
          });
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [selectedGuild?.id, selectedGuild?.name]);

  return (
    <Link
      href={`/${lang}/community/onboarding`}
      className="text-decoration-none d-block h-100"
    >
      <MetricWidget
        label="Verification"
        value={state.label}
        accent={state.accent}
        helper={state.helper}
        icon={<Icon icon={cilCheckCircle} size="lg" />}
      />
    </Link>
  );
}

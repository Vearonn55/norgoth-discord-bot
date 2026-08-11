"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CAlert, CSpinner } from "@coreui/react";
import { CampaignWizard } from "@/components/campaigns/campaign-wizard";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { Dictionary } from "@/app/[lang]/dictionaries";
import type { Locale } from "@/i18n/config";
import { apiUrl } from "@/lib/api";

type CampaignEditLoaderProps = {
  lang: Locale;
  dict: Dictionary;
  campaignId: string;
};

type EditableCampaign = {
  id: string;
  title?: string;
  message?: string;
  status?: string;
  delivery_target?: "channel" | "dm";
  discord_channel_id?: string | null;
  dm_include_role_ids?: string[];
  dm_exclude_role_ids?: string[];
  launch_at?: string | null;
  platform_messages?: {
    discord?: { type?: string; title?: string };
  };
  raw_payload?: { description?: string };
};

const NOT_EDITABLE_STATUSES = new Set(["queued", "running"]);

export function CampaignEditLoader({
  lang,
  dict,
  campaignId,
}: CampaignEditLoaderProps) {
  const [campaign, setCampaign] = useState<EditableCampaign | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadCampaign() {
      try {
        const response = await fetch(apiUrl(`/campaigns/${campaignId}`), {
          cache: "no-store",
        });

        if (response.status === 404) {
          if (!cancelled) setError("Campaign not found.");
          return;
        }

        if (!response.ok) {
          if (!cancelled) {
            setError("Could not load the campaign from the API.");
          }
          return;
        }

        const data = (await response.json()) as EditableCampaign;

        if (!cancelled) setCampaign(data);
      } catch {
        if (!cancelled) setError("Could not reach the Norgoth API.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadCampaign();

    return () => {
      cancelled = true;
    };
  }, [campaignId]);

  if (loading) {
    return (
      <Card>
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          Loading campaign…
        </div>
      </Card>
    );
  }

  if (error || !campaign) {
    return (
      <CAlert color="danger" className="mb-0">
        {error ?? "Campaign not found."}
        <div className="mt-3">
          <Link href={`/${lang}/campaigns`}>
            <Button variant="secondary" size="sm">
              Back to campaigns
            </Button>
          </Link>
        </div>
      </CAlert>
    );
  }

  if (NOT_EDITABLE_STATUSES.has(campaign.status ?? "")) {
    return (
      <CAlert color="warning" className="mb-0">
        This campaign is currently {campaign.status} and cannot be edited. Stop
        it first, or wait for delivery to finish.
        <div className="mt-3">
          <Link href={`/${lang}/campaigns/${campaign.id}`}>
            <Button variant="secondary" size="sm">
              Back to campaign
            </Button>
          </Link>
        </div>
      </CAlert>
    );
  }

  return <CampaignWizard lang={lang} dict={dict} editCampaign={campaign} />;
}

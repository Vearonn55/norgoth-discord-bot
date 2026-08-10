"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CAlert, CSpinner } from "@/components/ui/coreui";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TranscriptConversation } from "@/components/tickets/transcript-conversation";
import { apiUrl } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";

type SharedTranscript = {
  token: string;
  guild_name?: string | null;
  ticket_number?: number | null;
  opener_name?: string | null;
  opened_at?: string | null;
  closed_by?: string | null;
  closed_at?: string | null;
  channel_name?: string | null;
  panel_name?: string | null;
  transcript: string;
};

export default function TicketTranscriptPage() {
  const params = useParams();
  const lang = String(params?.lang || "en");
  const token = String(params?.token || "");
  const [data, setData] = useState<SharedTranscript | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setError("Missing transcript token.");
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(
          apiUrl(`/tickets/transcript/${encodeURIComponent(token)}`),
          { cache: "no-store" }
        );
        const body = await response.json().catch(() => null);

        if (!response.ok) {
          if (!cancelled) {
            setError(
              String(
                body?.detail ||
                  body?.error?.message ||
                  `Could not load transcript (HTTP ${response.status})`
              )
            );
          }
          return;
        }

        if (!cancelled) {
          setData(body as SharedTranscript);
        }
      } catch {
        if (!cancelled) {
          setError("Could not reach the API.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (loading) {
    return (
      <Card>
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          Loading transcript…
        </div>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <div className="d-flex flex-column gap-2">
          <Badge variant="warning">Transcript unavailable</Badge>
          <CAlert color="warning" className="mb-0">
            {error}
          </CAlert>
        </div>
      </Card>
    );
  }

  const metaItems: { label: string; value: string }[] = [
    {
      label: "Ticket",
      value: `#${data.ticket_number ?? "—"}`,
    },
    {
      label: "Server",
      value: data.guild_name || "—",
    },
    {
      label: "Channel",
      value: data.channel_name || "ticket",
    },
  ];
  if (data.panel_name) {
    metaItems.push({ label: "Panel", value: data.panel_name });
  }
  metaItems.push(
    { label: "Created by", value: data.opener_name || "unknown" },
    { label: "Opened at", value: formatDateTime(data.opened_at, lang) },
    { label: "Closed at", value: formatDateTime(data.closed_at, lang) },
    { label: "Closed by", value: data.closed_by || "—" },
    { label: "Status", value: "Closed" }
  );

  return (
    <div className="d-flex flex-column gap-4">
      <div className="d-flex flex-column gap-2">
        <h1 className="h3 mb-0 fw-semibold">Ticket Transcript</h1>
        <p className="mb-0 small text-body-secondary">
          A readable record of the closed support conversation.
        </p>
      </div>

      <Card>
        <div className="d-flex flex-column gap-3">
          <div className="d-flex align-items-center justify-content-between gap-2 flex-wrap">
            <h2 className="h5 mb-0 fw-semibold">
              Ticket #{data.ticket_number ?? "—"}
            </h2>
            <Badge variant="neutral">Closed</Badge>
          </div>
          <div className="row g-2">
            {metaItems.map((item) => (
              <div key={item.label} className="col-6 col-md-4 col-lg-3">
                <div className="small text-body-secondary">{item.label}</div>
                <div className="fw-medium text-break">{item.value}</div>
              </div>
            ))}
          </div>
        </div>
      </Card>

      <Card>
        <div className="d-flex flex-column gap-3">
          <h2 className="h6 mb-0 fw-semibold">Conversation</h2>
          <TranscriptConversation transcript={data.transcript} />
        </div>
      </Card>
    </div>
  );
}

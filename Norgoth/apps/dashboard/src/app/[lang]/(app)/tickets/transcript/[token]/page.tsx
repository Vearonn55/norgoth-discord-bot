"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CAlert, CSpinner } from "@/components/ui/coreui";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiUrl } from "@/lib/api";

type SharedTranscript = {
  token: string;
  guild_name?: string | null;
  ticket_number?: number | null;
  opener_name?: string | null;
  closed_by?: string | null;
  closed_at?: string | null;
  channel_name?: string | null;
  transcript: string;
};

export default function TicketTranscriptPage() {
  const params = useParams();
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

  return (
    <div className="d-flex flex-column gap-4">
      <div className="d-flex flex-column gap-2">
        <h1 className="h3 mb-0 fw-semibold">
          Ticket #{data.ticket_number ?? "—"} transcript
        </h1>
        <p className="mb-0 small text-body-secondary">
          {data.guild_name ? `${data.guild_name} · ` : ""}
          {data.channel_name || "ticket"} · opened by{" "}
          {data.opener_name || "unknown"}
          {data.closed_by ? ` · closed by ${data.closed_by}` : ""}
        </p>
      </div>

      <Card>
        <pre className="mb-0 overflow-auto font-monospace small text-break text-wrap" style={{ maxHeight: "70vh" }}>
          {data.transcript}
        </pre>
      </Card>
    </div>
  );
}

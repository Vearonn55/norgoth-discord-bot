"use client";

/**
 * Shared transcript parser + Discord-style conversation timeline.
 *
 * The bot stores transcripts as a flat newline-joined string:
 *   [YYYY-MM-DD HH:MM:SS] author: content [embed] <attachment urls>
 *
 * This module parses that format into readable message rows without requiring
 * a bot/payload schema change.
 */

import { useParams } from "next/navigation";
import { formatDateTime } from "@/lib/datetime";

export type TranscriptMessage = {
  timestamp: string;
  author: string;
  content: string;
  hasEmbed: boolean;
  attachments: string[];
};

const LINE_RE =
  /^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(.+?):\s*(.*)$/;

const URL_RE = /https?:\/\/\S+/g;

/**
 * Parse a flat transcript string into structured message rows.
 * Lines that do not match the expected format are kept as system rows.
 */
export function parseTranscript(raw: string): TranscriptMessage[] {
  const text = (raw ?? "").trim();
  if (!text || text === "(no messages)") {
    return [];
  }

  const rows: TranscriptMessage[] = [];
  for (const line of text.split("\n")) {
    const trimmed = line.trimEnd();
    if (!trimmed) continue;

    const match = trimmed.match(LINE_RE);
    if (!match) {
      rows.push({
        timestamp: "",
        author: "System",
        content: trimmed,
        hasEmbed: false,
        attachments: [],
      });
      continue;
    }

    const [, timestamp, author, rest] = match;
    const hasEmbed = /\s\[embed\]/.test(rest) || rest.trim() === "[embed]";
    let content = rest.replace(/\s?\[embed\]/g, "").trim();

    const attachments: string[] = [];
    const urls = content.match(URL_RE) ?? [];
    for (const url of urls) {
      // Treat bare URLs that look like Discord CDN attachments as attachments
      // and strip them from the visible content body.
      if (/cdn\.discordapp\.com|media\.discordapp\.net/i.test(url)) {
        attachments.push(url);
        content = content.replace(url, "").trim();
      }
    }

    rows.push({
      timestamp,
      author,
      content,
      hasEmbed,
      attachments,
    });
  }
  return rows;
}

function formatTimestamp(value: string, locale: string): string {
  if (!value) return "";
  // Prefer locale formatting when the ISO-ish stamp is parseable.
  const asIso = value.includes("T") ? value : value.replace(" ", "T") + "Z";
  return formatDateTime(asIso, locale);
}

type Props = {
  transcript: string;
  maxHeight?: string | number;
  className?: string;
};

export function TranscriptConversation({
  transcript,
  maxHeight = "70vh",
  className,
}: Props) {
  const params = useParams();
  const lang = String(params?.lang || "en");
  const messages = parseTranscript(transcript);

  if (messages.length === 0) {
    return (
      <div
        className={`border rounded p-3 text-body-secondary small ${className ?? ""}`}
      >
        No messages were recorded in this transcript.
      </div>
    );
  }

  return (
    <div
      className={`border rounded overflow-auto ${className ?? ""}`}
      style={{ maxHeight }}
    >
      <div className="d-flex flex-column gap-0 p-3">
        {messages.map((message, index) => {
          const previous = index > 0 ? messages[index - 1] : null;
          const grouped =
            previous != null &&
            previous.author === message.author &&
            previous.timestamp.slice(0, 16) === message.timestamp.slice(0, 16);

          return (
            <div
              key={`${message.timestamp}-${message.author}-${index}`}
              className={`d-flex gap-3 ${grouped ? "pt-1" : "pt-3"}`}
              style={index === 0 ? { paddingTop: 0 } : undefined}
            >
              <div
                className="flex-shrink-0 rounded-circle d-flex align-items-center justify-content-center text-white fw-semibold"
                style={{
                  width: 36,
                  height: 36,
                  fontSize: 13,
                  background:
                    "linear-gradient(135deg, var(--cui-primary), var(--cui-info))",
                  visibility: grouped ? "hidden" : "visible",
                }}
                aria-hidden={grouped}
              >
                {(message.author || "?").slice(0, 1).toUpperCase()}
              </div>
              <div className="flex-grow-1 min-w-0">
                {!grouped ? (
                  <div className="d-flex align-items-baseline gap-2 flex-wrap mb-1">
                    <span className="fw-semibold">{message.author}</span>
                    {message.timestamp ? (
                      <span className="small text-body-secondary">
                        {formatTimestamp(message.timestamp, lang)}
                      </span>
                    ) : null}
                  </div>
                ) : null}
                {message.content ? (
                  <div
                    className="text-break"
                    style={{ whiteSpace: "pre-wrap", lineHeight: 1.45 }}
                  >
                    {message.content}
                  </div>
                ) : null}
                {message.hasEmbed ? (
                  <div className="small text-body-secondary mt-1">
                    [embed attached]
                  </div>
                ) : null}
                {message.attachments.length > 0 ? (
                  <div className="d-flex flex-column gap-1 mt-1">
                    {message.attachments.map((url) => (
                      <a
                        key={url}
                        href={url}
                        target="_blank"
                        rel="noreferrer"
                        className="small text-break"
                      >
                        {url}
                      </a>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

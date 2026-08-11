"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CFormInput } from "@coreui/react";
import {
  SKIN_TONE_SWATCHES,
  UNICODE_EMOJI_CATEGORY_META,
  emojiPreviewSrc,
  encodeGuildEmoji,
  filterUnicodeEmojis,
  getRecentEmojis,
  getUnicodeEmojiCategoriesSync,
  loadUnicodeEmojiCategories,
  pushRecentEmoji,
  resolveEmojiChar,
  type EmojiCategory,
  type GuildEmojiItem,
} from "@/lib/discord/emoji-data";

type DiscordEmojiPickerProps = {
  value: string;
  onChange: (value: string) => void;
  guildEmojis?: GuildEmojiItem[];
  placeholder?: string;
  required?: boolean;
};

export function DiscordEmojiPicker({
  value,
  onChange,
  guildEmojis = [],
  placeholder = "Pick an emoji",
  required = false,
}: DiscordEmojiPickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [recent, setRecent] = useState<string[]>([]);
  const [category, setCategory] = useState<string>("people");
  const [categories, setCategories] = useState<EmojiCategory[]>(
    () => getUnicodeEmojiCategoriesSync()
  );
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [skinTone, setSkinTone] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setRecent(getRecentEmojis());
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (categories.length > 0) return;

    let cancelled = false;
    setCatalogLoading(true);
    setCatalogError(null);
    loadUnicodeEmojiCategories()
      .then((loaded) => {
        if (cancelled) return;
        setCategories(loaded);
      })
      .catch(() => {
        if (cancelled) return;
        setCatalogError("Could not load emoji catalog.");
      })
      .finally(() => {
        if (!cancelled) setCatalogLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, categories.length]);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const preview = emojiPreviewSrc(value);

  const filteredUnicode = useMemo(
    () => filterUnicodeEmojis(query, categories),
    [query, categories]
  );

  const filteredGuild = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return guildEmojis;
    return guildEmojis.filter((e) => e.name.toLowerCase().includes(q));
  }, [guildEmojis, query]);

  function select(next: string) {
    onChange(next);
    pushRecentEmoji(next);
    setRecent(getRecentEmojis());
    setOpen(false);
    setQuery("");
  }

  const categoryTabs = [
    ...(recent.length ? [{ id: "recent", label: "Recent" }] : []),
    ...(guildEmojis.length ? [{ id: "server", label: "Server" }] : []),
    ...(categories.length
      ? categories.map((c) => ({ id: c.id, label: c.label }))
      : UNICODE_EMOJI_CATEGORY_META),
  ];

  const standardList = query
    ? filteredUnicode
    : (categories.find((c) => c.id === category)?.emojis ?? []);

  return (
    <div className="norgoth-discord-emoji-picker position-relative" ref={rootRef}>
      <button
        type="button"
        className="btn btn-outline-secondary d-inline-flex align-items-center gap-2"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((v) => !v)}
      >
        {preview.type === "unicode" ? (
          <span style={{ fontSize: "1.25rem" }} aria-hidden>
            {preview.text}
          </span>
        ) : preview.type === "image" ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={preview.url}
            alt={preview.text ?? "emoji"}
            width={22}
            height={22}
          />
        ) : (
          <span className="small text-body-secondary">{placeholder}</span>
        )}
        <span className="small">{value ? "Change" : "Choose"}</span>
      </button>

      {value ? (
        <button
          type="button"
          className="btn btn-link btn-sm"
          onClick={() => onChange("")}
        >
          Clear
        </button>
      ) : required ? (
        <span className="small text-warning ms-2">Required</span>
      ) : null}

      {open ? (
        <div
          className="norgoth-emoji-popover border rounded shadow p-2"
          role="dialog"
          aria-label="Emoji picker"
        >
          <CFormInput
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search emoji…"
            className="mb-2"
          />

          <div className="d-flex flex-wrap align-items-center gap-1 mb-2">
            <span className="small text-body-secondary me-1">Tone</span>
            {SKIN_TONE_SWATCHES.map((swatch, index) => (
              <button
                key={swatch}
                type="button"
                className={[
                  "btn btn-sm",
                  skinTone === index ? "btn-primary" : "btn-outline-secondary",
                ].join(" ")}
                aria-label={`Skin tone ${index + 1}`}
                aria-pressed={skinTone === index}
                onClick={() => setSkinTone(index)}
              >
                {swatch}
              </button>
            ))}
          </div>

          <div className="d-flex flex-wrap gap-1 mb-2">
            {categoryTabs.map((cat) => (
              <button
                key={cat.id}
                type="button"
                className={[
                  "btn btn-sm",
                  category === cat.id ? "btn-primary" : "btn-outline-secondary",
                ].join(" ")}
                onClick={() => setCategory(cat.id)}
              >
                {cat.label}
              </button>
            ))}
          </div>

          <div
            className="norgoth-emoji-grid"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(8, 1fr)",
              gap: 4,
              maxHeight: 220,
              overflowY: "auto",
            }}
          >
            {category === "recent"
              ? recent.map((item) => {
                  const p = emojiPreviewSrc(item);
                  return (
                    <button
                      key={item}
                      type="button"
                      className="btn btn-sm btn-outline-secondary"
                      onClick={() => select(item)}
                      title={item}
                    >
                      {p.type === "image" ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={p.url} alt="" width={20} height={20} />
                      ) : (
                        p.text
                      )}
                    </button>
                  );
                })
              : null}

            {category === "server"
              ? filteredGuild.map((emoji) => {
                  const encoded = encodeGuildEmoji(emoji);
                  const ext = emoji.animated ? "gif" : "png";
                  return (
                    <button
                      key={emoji.id}
                      type="button"
                      className="btn btn-sm btn-outline-secondary"
                      onClick={() => select(encoded)}
                      title={emoji.name}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={`https://cdn.discordapp.com/emojis/${emoji.id}.${ext}?size=32`}
                        alt={emoji.name}
                        width={20}
                        height={20}
                      />
                    </button>
                  );
                })
              : null}

            {category !== "recent" && category !== "server"
              ? standardList.map((emoji) => {
                  const char = resolveEmojiChar(emoji, skinTone);
                  return (
                    <button
                      key={emoji.id}
                      type="button"
                      className="btn btn-sm btn-outline-secondary"
                      onClick={() => select(char)}
                      title={emoji.name}
                    >
                      {char}
                    </button>
                  );
                })
              : null}
          </div>

          {catalogLoading && category !== "recent" && category !== "server" ? (
            <p className="mb-0 mt-2 small text-body-secondary">Loading emoji…</p>
          ) : null}

          {catalogError ? (
            <p className="mb-0 mt-2 small text-danger">{catalogError}</p>
          ) : null}

          {category === "server" && filteredGuild.length === 0 ? (
            <p className="mb-0 mt-2 small text-body-secondary">
              {guildEmojis.length === 0
                ? "No custom server emoji available yet."
                : "No server emoji match your search."}
            </p>
          ) : null}

          {category !== "recent" &&
          category !== "server" &&
          !catalogLoading &&
          !catalogError &&
          standardList.length === 0 ? (
            <p className="mb-0 mt-2 small text-body-secondary">
              No emoji match your search.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

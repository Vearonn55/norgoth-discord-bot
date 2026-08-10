"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CSpinner } from "@coreui/react";
import { EmbedDraftCreator } from "@/components/embed-messages/embed-draft-creator";
import { useFirstGuild } from "@/lib/use-first-guild";
import {
  useEmbedMessagesStore,
  type EmbedMessage,
} from "@/stores/embed-messages-store";

type Props = {
  lang: string;
  messageId: string;
};

/**
 * Full-page host for the shared `EmbedDraftCreator`. Handles route-level
 * concerns (loading an existing draft, navigation) and delegates all authoring
 * to the shared creator so the modal and Self-Assignable Roles flows behave
 * identically.
 */
export function EmbedMessageEditor({ lang, messageId }: Props) {
  const router = useRouter();
  const { guildId, resources } = useFirstGuild();
  const isNew = messageId === "new";

  const getMessage = useEmbedMessagesStore((s) => s.get);

  const [loading, setLoading] = useState(!isNew);
  const [message, setMessage] = useState<EmbedMessage | null>(null);

  useEffect(() => {
    if (isNew || !guildId) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    void getMessage(guildId, messageId).then((loaded) => {
      if (!active) return;
      if (loaded) setMessage(loaded);
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [guildId, isNew, messageId, getMessage]);

  if (loading) {
    return (
      <div className="d-flex justify-content-center py-5">
        <CSpinner />
      </div>
    );
  }

  const channels = resources?.channels ?? [];
  const backToList = () => router.push(`/${lang}/messages/embed-messages`);

  return (
    <EmbedDraftCreator
      guildId={guildId}
      channels={channels}
      mode={isNew ? "create" : "edit"}
      messageId={isNew ? undefined : messageId}
      initialMessage={isNew ? null : message}
      onCreated={(created) =>
        router.replace(`/${lang}/messages/embed-messages/${created.id}`)
      }
      onCancel={backToList}
    />
  );
}

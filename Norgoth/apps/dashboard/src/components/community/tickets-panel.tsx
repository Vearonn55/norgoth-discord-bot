"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  CAlert,
  CCol,
  CFormInput,
  CFormLabel,
  CFormSelect,
  CRow,
  CSpinner,
} from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RoleMultiPicker } from "@/components/ui/role-multi-picker";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { TranscriptConversation } from "@/components/tickets/transcript-conversation";
import { EmbedDraftCreator } from "@/components/embed-messages/embed-draft-creator";
import { TicketPanelPreview } from "@/components/community/ticket-panel-preview";
import { MessageSourceToggle } from "@/components/discord/message-source-toggle";
import { RichMessageEditor } from "@/components/editors/rich-message-editor";
import { formatDateTime } from "@/lib/datetime";
import { useFirstGuild } from "@/lib/use-first-guild";
import {
  useEmbedMessagesStore,
  type EmbedMessage,
} from "@/stores/embed-messages-store";
import {
  newTicketPanel,
  useTicketsStore,
  type TicketPanel,
} from "@/stores/tickets-store";

type EmbedSourceMode = "NONE" | "SELECT_EXISTING" | "CREATE_NEW";

export function TicketsPanel() {
  const params = useParams();
  const lang = String(params?.lang || "en");
  const { guildId, resources, loading, error, reload } = useFirstGuild();

  const config = useTicketsStore((s) => s.config);
  const tickets = useTicketsStore((s) => s.tickets);
  const panels = useTicketsStore((s) => s.panels);
  const editingPanel = useTicketsStore((s) => s.editingPanel);
  const panelsSaving = useTicketsStore((s) => s.panelsSaving);
  const publishingPanelId = useTicketsStore((s) => s.publishingPanelId);
  const saving = useTicketsStore((s) => s.saving);
  const feedback = useTicketsStore((s) => s.feedback);
  const feedbackIsError = useTicketsStore((s) => s.feedbackIsError);
  const transcript = useTicketsStore((s) => s.transcript);
  const setConfig = useTicketsStore((s) => s.setConfig);
  const setTranscript = useTicketsStore((s) => s.setTranscript);
  const setEditingPanel = useTicketsStore((s) => s.setEditingPanel);
  const load = useTicketsStore((s) => s.load);
  const save = useTicketsStore((s) => s.save);
  const saveEditingPanel = useTicketsStore((s) => s.saveEditingPanel);
  const deletePanel = useTicketsStore((s) => s.deletePanel);
  const publishPanelById = useTicketsStore((s) => s.publishPanelById);
  const viewTranscript = useTicketsStore((s) => s.viewTranscript);

  const embedMessages = useEmbedMessagesStore((s) => s.messages);
  const embedLoading = useEmbedMessagesStore((s) => s.loading);
  const loadEmbeds = useEmbedMessagesStore((s) => s.load);

  const [pendingDeletePanel, setPendingDeletePanel] =
    useState<TicketPanel | null>(null);
  const [embedSourceMode, setEmbedSourceMode] =
    useState<EmbedSourceMode>("NONE");
  const [draftSearch, setDraftSearch] = useState("");
  const [creatorKey, setCreatorKey] = useState(0);

  useEffect(() => {
    if (!guildId) return;
    void load(guildId);
  }, [guildId, load]);

  useEffect(() => {
    if (!guildId || editingPanel === null) return;
    void loadEmbeds(guildId);
    setEmbedSourceMode(
      editingPanel.message_source === "embed" && editingPanel.embed_message_id
        ? "SELECT_EXISTING"
        : editingPanel.message_source === "embed"
          ? "NONE"
          : "NONE"
    );
    setDraftSearch("");
  }, [guildId, editingPanel?.id, loadEmbeds]); // eslint-disable-line react-hooks/exhaustive-deps

  const selectedDraft: EmbedMessage | undefined = useMemo(
    () =>
      embedMessages.find((m) => m.id === editingPanel?.embed_message_id),
    [embedMessages, editingPanel?.embed_message_id]
  );

  const filteredDrafts = useMemo(() => {
    const q = draftSearch.trim().toLowerCase();
    if (!q) return embedMessages;
    return embedMessages.filter((m) =>
      `${m.name} ${m.description}`.toLowerCase().includes(q)
    );
  }, [embedMessages, draftSearch]);

  if (loading) {
    return (
      <Card>
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          <span>Loading ticket settings…</span>
        </div>
      </Card>
    );
  }

  if (error || !guildId) {
    return (
      <Card>
        <div className="d-flex flex-column gap-3">
          <Badge variant="warning">Bot required</Badge>
          <p className="mb-0 text-body-secondary">{error}</p>
          <Button variant="secondary" onClick={() => void reload()}>
            Retry
          </Button>
        </div>
      </Card>
    );
  }

  const channels = resources?.channels ?? [];
  const categories = resources?.categories ?? [];
  const roles = (resources?.roles ?? []).filter((role) => !role.managed);
  const openTickets = tickets.filter((ticket) => ticket.status === "open");
  const channelName = (id: string | null) =>
    id ? channels.find((channel) => channel.id === id)?.name ?? id : null;

  const openCategoryMissing = Boolean(
    editingPanel?.open_category_id &&
      !categories.some(
        (category) => category.id === editingPanel.open_category_id
      )
  );

  const embedMissing = Boolean(
    editingPanel?.embed_message_id && !embedLoading && !selectedDraft
  );

  return (
    <div className="d-flex flex-column gap-4">
      <div className="row g-3 align-items-start">
        <div className="col-12 col-lg-4">
          <Card className="h-100">
            <div className="d-flex flex-column gap-2">
              <div>
                <h2 className="h5 mb-1">Ticket Support Role</h2>
                <p className="mb-0 text-body-secondary small">
                  Roles that can see every ticket, plus the welcome text posted
                  inside new tickets.
                </p>
              </div>

              <div>
                <CFormLabel className="mb-1 small">Support roles</CFormLabel>
                <RoleMultiPicker
                  roles={roles}
                  selectedIds={config.support_role_ids}
                  onChange={(ids) =>
                    setConfig((current) => ({
                      ...current,
                      support_role_ids: ids.slice(0, 20),
                    }))
                  }
                  maxSelected={20}
                  pageSize={4}
                  searchPlaceholder="Search support roles…"
                />
              </div>

              <div>
                <CFormLabel className="mb-1 small">
                  Message inside new tickets
                </CFormLabel>
                <RichMessageEditor
                  key="ticket-welcome-editor"
                  value={config.welcome_text}
                  onChange={(markdown) =>
                    setConfig((current) => ({
                      ...current,
                      welcome_text: markdown.trim() ? markdown : "",
                    }))
                  }
                  height={160}
                  placeholder="Support will be with you shortly…"
                />
                <p className="mt-1 mb-0 small text-body-secondary">
                  {config.welcome_text.length}/1000 characters
                </p>
              </div>

              <div className="d-flex flex-wrap align-items-center gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => void save(guildId)}
                  disabled={saving}
                >
                  {saving ? "Saving…" : "Save Settings"}
                </Button>

                {feedback ? (
                  <CAlert
                    color={feedbackIsError ? "danger" : "success"}
                    className="mb-0 py-1 px-2 small"
                  >
                    {feedback}
                  </CAlert>
                ) : null}
              </div>
            </div>
          </Card>
        </div>

        <div className="col-12 col-lg-8">
          <Card className="h-100">
            <div className="d-flex flex-column gap-3">
              <div className="d-flex align-items-center justify-content-between gap-3">
                <div>
                  <h2 className="h5 mb-1">Ticket Panels</h2>
                  <p className="mb-0 text-body-secondary small">
                    Each panel posts an Open Ticket button. Bind an Embed
                    Library draft for the message visual.
                  </p>
                </div>

                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    setEditingPanel(newTicketPanel());
                    setEmbedSourceMode("NONE");
                    setCreatorKey((k) => k + 1);
                  }}
                >
                  New panel
                </Button>
              </div>

              {panels.length === 0 ? (
                <CAlert color="secondary" className="mb-0">
                  No panels yet. Create one to give members a button that opens
                  a ticket.
                </CAlert>
              ) : (
                <div className="d-flex flex-column gap-2">
                  {panels.map((panel) => (
                    <div
                      key={panel.id}
                      className="d-flex flex-column flex-md-row align-items-md-center justify-content-md-between gap-2 border rounded p-3"
                    >
                      <div className="d-flex flex-wrap align-items-center gap-3">
                        <Badge
                          variant={panel.message_id ? "success" : "neutral"}
                        >
                          {panel.message_id ? "Published" : "Draft"}
                        </Badge>
                        <span className="fw-medium">{panel.name}</span>
                        <span className="text-body-secondary small">
                          {channelName(panel.channel_id)
                            ? `#${channelName(panel.channel_id)}`
                            : "No channel set"}
                        </span>
                      </div>

                      <div className="d-flex flex-wrap align-items-center gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => setEditingPanel({ ...panel })}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() =>
                            void publishPanelById(guildId, panel.id)
                          }
                          disabled={
                            publishingPanelId === panel.id || !panel.channel_id
                          }
                        >
                          {publishingPanelId === panel.id
                            ? "Publishing…"
                            : panel.message_id
                              ? "Update"
                              : "Publish"}
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => setPendingDeletePanel(panel)}
                          disabled={panelsSaving}
                        >
                          Delete
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>

      <Card>
        <div className="d-flex flex-column gap-3">
          <div className="d-flex align-items-center justify-content-between gap-3">
            <div>
              <h2 className="h5 mb-1">Tickets</h2>
              <p className="mb-0 text-body-secondary small">
                {openTickets.length} open · {tickets.length} total
              </p>
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => void load(guildId)}
            >
              Refresh
            </Button>
          </div>

          {tickets.length === 0 ? (
            <CAlert color="secondary" className="mb-0">
              No tickets yet. Publish the panel and members can open tickets
              from Discord.
            </CAlert>
          ) : (
            <div className="d-flex flex-column gap-2">
              {tickets.map((ticket) => (
                <div
                  key={ticket.id}
                  className="d-flex flex-column flex-md-row align-items-md-center justify-content-md-between gap-2 border rounded p-3"
                >
                  <div className="d-flex flex-wrap align-items-center gap-3">
                    <Badge
                      variant={ticket.status === "open" ? "success" : "neutral"}
                    >
                      {ticket.status}
                    </Badge>
                    <span className="fw-medium">
                      #{String(ticket.number).padStart(4, "0")}
                    </span>
                    <span className="text-body-secondary">
                      {ticket.opener_name}
                    </span>
                  </div>

                  <div className="d-flex align-items-center gap-3 small text-body-secondary">
                    <span>
                      Opened {formatDateTime(ticket.opened_at, lang)}
                    </span>
                    {ticket.status === "closed" ? (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => void viewTranscript(guildId, ticket)}
                      >
                        Transcript
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      {transcript ? (
        <Card>
          <div className="d-flex flex-column gap-3">
            <div className="d-flex align-items-center justify-content-between gap-3">
              <h3 className="h6 mb-0">
                Transcript — Ticket #
                {String(transcript.ticketNumber).padStart(4, "0")}
              </h3>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setTranscript(null)}
              >
                Close
              </Button>
            </div>
            <TranscriptConversation
              transcript={transcript.text}
              maxHeight="24rem"
            />
          </div>
        </Card>
      ) : null}

      <FeatureConfigurationModal
        visible={editingPanel !== null}
        title={editingPanel ? "Edit ticket panel" : "Ticket panel"}
        description="Configure channel, category, Open Ticket button, and the panel message (plain text or Embed Library draft)."
        category="community"
        icon="cilChatBubble"
        onClose={() => {
          setEditingPanel(null);
          setEmbedSourceMode("NONE");
        }}
        onSave={async () => {
          await saveEditingPanel(guildId);
        }}
        saving={panelsSaving}
        saveLabel="Save panel"
        size="xl"
        saveDisabled={
          !editingPanel ||
          (editingPanel.message_source === "embed" &&
            !editingPanel.embed_message_id &&
            embedSourceMode !== "CREATE_NEW") ||
          (editingPanel.message_source === "text" &&
            !editingPanel.text_content.trim())
        }
      >
        {editingPanel ? (
          <div className="d-flex flex-column gap-3">
            <CRow className="g-3">
              <CCol md={6}>
                <CFormLabel>Panel name (internal)</CFormLabel>
                <CFormInput
                  value={editingPanel.name}
                  onChange={(event) =>
                    setEditingPanel((current) =>
                      current
                        ? { ...current, name: event.target.value }
                        : current
                    )
                  }
                  maxLength={100}
                />
              </CCol>
              <CCol md={6}>
                <CFormLabel>Channel</CFormLabel>
                <CFormSelect
                  value={editingPanel.channel_id ?? ""}
                  onChange={(event) =>
                    setEditingPanel((current) =>
                      current
                        ? {
                            ...current,
                            channel_id: event.target.value || null,
                          }
                        : current
                    )
                  }
                >
                  <option value="">Select a channel…</option>
                  {channels.map((channel) => (
                    <option key={channel.id} value={channel.id}>
                      #{channel.name}
                    </option>
                  ))}
                </CFormSelect>
              </CCol>
            </CRow>

            <CRow className="g-3">
              <CCol md={6}>
                <CFormLabel>Open ticket category</CFormLabel>
                <CFormSelect
                  value={editingPanel.open_category_id ?? ""}
                  onChange={(event) =>
                    setEditingPanel((current) =>
                      current
                        ? {
                            ...current,
                            open_category_id: event.target.value || null,
                          }
                        : current
                    )
                  }
                >
                  <option value="">No category (top level)</option>
                  {openCategoryMissing ? (
                    <option value={editingPanel.open_category_id ?? ""}>
                      Unavailable (id {editingPanel.open_category_id})
                    </option>
                  ) : null}
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </CFormSelect>
              </CCol>
              <CCol md={6}>
                <CFormLabel>Button label</CFormLabel>
                <CFormInput
                  value={editingPanel.button_label}
                  onChange={(event) =>
                    setEditingPanel((current) =>
                      current
                        ? { ...current, button_label: event.target.value }
                        : current
                    )
                  }
                  maxLength={80}
                />
              </CCol>
            </CRow>

            {openCategoryMissing ? (
              <CAlert color="warning" className="mb-0 py-2">
                A previously selected category no longer exists in this server.
                Pick a replacement before publishing.
              </CAlert>
            ) : null}

            <div>
              <div className="d-flex align-items-center justify-content-between gap-2 mb-2">
                <CFormLabel className="fw-medium mb-0">Panel message</CFormLabel>
                <MessageSourceToggle
                  value={editingPanel.message_source}
                  onChange={(next) => {
                    setEditingPanel((current) =>
                      current
                        ? { ...current, message_source: next }
                        : current
                    );
                    if (next === "embed") {
                      setEmbedSourceMode(
                        editingPanel.embed_message_id
                          ? "SELECT_EXISTING"
                          : "NONE"
                      );
                    }
                  }}
                />
              </div>

              {editingPanel.message_source === "text" ? (
                <RichMessageEditor
                  key={`ticket-text-${editingPanel.id}`}
                  value={editingPanel.text_content}
                  onChange={(markdown) =>
                    setEditingPanel((current) =>
                      current
                        ? { ...current, text_content: markdown }
                        : current
                    )
                  }
                  height={180}
                  placeholder="Write the panel message members will see…"
                />
              ) : (
                <>
                  <div className="d-flex flex-wrap gap-2 mt-1 mb-2">
                    <Button
                      variant={
                        embedSourceMode === "SELECT_EXISTING"
                          ? "primary"
                          : "secondary"
                      }
                      size="sm"
                      onClick={() => setEmbedSourceMode("SELECT_EXISTING")}
                    >
                      Select From Draft
                    </Button>
                    <Button
                      variant={
                        embedSourceMode === "CREATE_NEW"
                          ? "primary"
                          : "secondary"
                      }
                      size="sm"
                      onClick={() => {
                        setEmbedSourceMode("CREATE_NEW");
                        setCreatorKey((k) => k + 1);
                      }}
                    >
                      Create New
                    </Button>
                  </div>

                  {embedSourceMode === "NONE" ? (
                    <p className="small text-body-secondary mb-0">
                      Choose an Embed Library draft for this panel&apos;s
                      message, or create a new one without leaving Tickets.
                    </p>
                  ) : null}

                  {embedSourceMode === "SELECT_EXISTING" ? (
                    <div className="d-flex flex-column gap-2">
                      <CFormInput
                        value={draftSearch}
                        onChange={(e) => setDraftSearch(e.target.value)}
                        placeholder="Search drafts…"
                        aria-label="Search Embed Library drafts"
                      />
                      <CFormSelect
                        value={editingPanel.embed_message_id ?? ""}
                        onChange={(event) =>
                          setEditingPanel((current) =>
                            current
                              ? {
                                  ...current,
                                  embed_message_id:
                                    event.target.value || null,
                                }
                              : current
                          )
                        }
                      >
                        <option value="">Select a draft…</option>
                        {filteredDrafts.map((draft) => (
                          <option key={draft.id} value={draft.id}>
                            {draft.name}
                          </option>
                        ))}
                      </CFormSelect>
                      {embedMessages.length === 0 && !embedLoading ? (
                        <p className="small text-body-secondary mb-0">
                          No Embed Library drafts yet. Use Create New.
                        </p>
                      ) : null}
                    </div>
                  ) : null}

                  {embedSourceMode === "CREATE_NEW" ? (
                    <EmbedDraftCreator
                      key={creatorKey}
                      guildId={guildId}
                      channels={channels}
                      mode="create"
                      compact
                      createLabel="Save Draft"
                      cancelLabel="Back"
                      onCancel={() =>
                        setEmbedSourceMode(
                          editingPanel.embed_message_id
                            ? "SELECT_EXISTING"
                            : "NONE"
                        )
                      }
                      onCreated={(created) => {
                        setEditingPanel((current) =>
                          current
                            ? { ...current, embed_message_id: created.id }
                            : current
                        );
                        setEmbedSourceMode("SELECT_EXISTING");
                        void loadEmbeds(guildId);
                      }}
                    />
                  ) : null}
                </>
              )}
            </div>

            {editingPanel.message_source === "text" ||
            embedSourceMode !== "CREATE_NEW" ? (
              <TicketPanelPreview
                mode={editingPanel.message_source}
                content={
                  editingPanel.message_source === "text"
                    ? editingPanel.text_content
                    : selectedDraft?.content
                }
                embed={
                  editingPanel.message_source === "embed"
                    ? selectedDraft?.embed_json
                    : null
                }
                buttonLabel={editingPanel.button_label}
                embedLoading={
                  editingPanel.message_source === "embed" &&
                  embedLoading &&
                  Boolean(editingPanel.embed_message_id)
                }
                embedMissing={
                  editingPanel.message_source === "embed" && embedMissing
                }
                noDraft={
                  editingPanel.message_source === "embed" &&
                  !editingPanel.embed_message_id
                }
              />
            ) : null}

            {editingPanel.channel_id ? null : (
              <CAlert color="secondary" className="mb-0 py-2">
                Choose a channel before publishing this panel.
              </CAlert>
            )}
          </div>
        ) : null}
      </FeatureConfigurationModal>

      <ConfirmDialog
        visible={pendingDeletePanel !== null}
        title="Delete Ticket Panel?"
        message={
          <p className="mb-0 text-body-secondary">
            This deletes the panel <strong>{pendingDeletePanel?.name}</strong>.
            {pendingDeletePanel?.message_id
              ? " Its published Open Ticket button will stop working; remove the message in Discord if it is still posted."
              : ""}{" "}
            This cannot be undone.
          </p>
        }
        confirmLabel="Delete Panel"
        destructive
        busy={panelsSaving}
        onConfirm={async () => {
          if (!pendingDeletePanel) return;
          await deletePanel(guildId, pendingDeletePanel.id);
          if (!useTicketsStore.getState().feedbackIsError) {
            setPendingDeletePanel(null);
          }
        }}
        onCancel={() => setPendingDeletePanel(null)}
      />
    </div>
  );
}

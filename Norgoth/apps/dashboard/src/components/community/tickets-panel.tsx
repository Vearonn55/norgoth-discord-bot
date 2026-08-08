"use client";

import { useEffect, useState } from "react";
import {
  CAlert,
  CCol,
  CFormInput,
  CFormLabel,
  CFormSelect,
  CFormTextarea,
  CRow,
  CSpinner,
} from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RoleMultiPicker } from "@/components/ui/role-multi-picker";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { useFirstGuild } from "@/lib/use-first-guild";
import {
  newTicketPanel,
  useTicketsStore,
  type TicketPanel,
} from "@/stores/tickets-store";

export function TicketsPanel() {
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

  const [pendingDeletePanel, setPendingDeletePanel] =
    useState<TicketPanel | null>(null);

  useEffect(() => {
    if (!guildId) return;
    void load(guildId);
  }, [guildId, load]);

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

  return (
    <div className="d-flex flex-column gap-4">
      <Card>
        <div className="d-flex flex-column gap-3">
          <div>
            <h2 className="h5 mb-1">Ticket Settings</h2>
            <p className="mb-0 text-body-secondary small">
              Shared configuration for every ticket. Create one or more panels
              below; each click on a panel button opens a private channel for
              the member and your support roles.
            </p>
          </div>

          <CRow className="g-3">
            <CCol md={6}>
              <CFormLabel>Open-ticket category</CFormLabel>
              <CFormSelect
                value={config.category_id ?? ""}
                onChange={(event) =>
                  setConfig((current) => ({
                    ...current,
                    category_id: event.target.value || null,
                  }))
                }
              >
                <option value="">No category (top level)</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </CFormSelect>
              <p className="mt-2 mb-0 small text-body-secondary">
                New ticket channels are created under this Discord category.
              </p>
            </CCol>

            <CCol md={6}>
              <CFormLabel>Closed-ticket log channel</CFormLabel>
              <CFormSelect
                value={config.log_channel_id ?? ""}
                onChange={(event) =>
                  setConfig((current) => ({
                    ...current,
                    log_channel_id: event.target.value || null,
                  }))
                }
              >
                <option value="">None</option>
                {channels.map((channel) => (
                  <option key={channel.id} value={channel.id}>
                    #{channel.name}
                  </option>
                ))}
              </CFormSelect>
              <p className="mt-2 mb-0 small text-body-secondary">
                Admins get a closed-ticket summary with a transcript link here.
              </p>
            </CCol>
          </CRow>

          <div>
            <CFormLabel className="mb-2">
              Support roles (can see all tickets)
            </CFormLabel>
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
              searchPlaceholder="Search support roles…"
            />
          </div>

          <div>
            <CFormLabel>Message posted inside each new ticket</CFormLabel>
            <CFormTextarea
              value={config.welcome_text}
              onChange={(event) =>
                setConfig((current) => ({
                  ...current,
                  welcome_text: event.target.value,
                }))
              }
              maxLength={1000}
              rows={3}
            />
          </div>

          <div className="d-flex flex-wrap align-items-center gap-3">
            <Button
              variant="primary"
              onClick={() => void save(guildId)}
              disabled={saving}
            >
              {saving ? "Saving…" : "Save Settings"}
            </Button>

            {feedback ? (
              <CAlert
                color={feedbackIsError ? "danger" : "success"}
                className="mb-0 py-2"
              >
                {feedback}
              </CAlert>
            ) : null}
          </div>
        </div>
      </Card>

      <Card>
        <div className="d-flex flex-column gap-3">
          <div className="d-flex align-items-center justify-content-between gap-3">
            <div>
              <h2 className="h5 mb-1">Ticket Panels</h2>
              <p className="mb-0 text-body-secondary small">
                Each panel posts its own Open Ticket button to a channel.
                Publish to post it, or re-publish to update the existing
                message in place.
              </p>
            </div>

            <Button
              variant="primary"
              size="sm"
              onClick={() => setEditingPanel(newTicketPanel())}
            >
              New panel
            </Button>
          </div>

          {panels.length === 0 ? (
            <CAlert color="secondary" className="mb-0">
              No panels yet. Create one to give members a button that opens a
              ticket.
            </CAlert>
          ) : (
            <div className="d-flex flex-column gap-2">
              {panels.map((panel) => (
                <div
                  key={panel.id}
                  className="d-flex flex-column flex-md-row align-items-md-center justify-content-md-between gap-2 border rounded p-3"
                >
                  <div className="d-flex flex-wrap align-items-center gap-3">
                    <Badge variant={panel.message_id ? "success" : "neutral"}>
                      {panel.message_id ? "Published" : "Draft"}
                    </Badge>
                    <span className="fw-medium">{panel.name}</span>
                    <span className="text-body-secondary small">
                      {channelName(panel.channel_id)
                        ? `#${channelName(panel.channel_id)}`
                        : "No channel set"}
                    </span>
                    <span className="text-body-tertiary small">
                      {panel.published_at
                        ? `Published ${new Date(panel.published_at).toLocaleString()}`
                        : panel.updated_at
                          ? `Updated ${new Date(panel.updated_at).toLocaleString()}`
                          : "Never published"}
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
                      onClick={() => void publishPanelById(guildId, panel.id)}
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
                      Opened {new Date(ticket.opened_at).toLocaleString()}
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
            <pre className="border rounded p-3 small mb-0 overflow-auto" style={{ maxHeight: "24rem" }}>
              {transcript.text}
            </pre>
          </div>
        </Card>
      ) : null}

      <FeatureConfigurationModal
        visible={editingPanel !== null}
        title={editingPanel ? "Edit ticket panel" : "Ticket panel"}
        description="Configure the button members click to open a ticket. Publish this panel from the list to post or update it in Discord."
        category="community"
        icon="cilChatBubble"
        onClose={() => setEditingPanel(null)}
        onSave={async () => {
          await saveEditingPanel(guildId);
        }}
        saving={panelsSaving}
        saveLabel="Save panel"
        size="lg"
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
                      current ? { ...current, name: event.target.value } : current
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
                        ? { ...current, channel_id: event.target.value || null }
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

            <div>
              <CFormLabel>Panel title</CFormLabel>
              <CFormInput
                value={editingPanel.title}
                onChange={(event) =>
                  setEditingPanel((current) =>
                    current ? { ...current, title: event.target.value } : current
                  )
                }
                maxLength={256}
              />
            </div>

            <div>
              <CFormLabel>Panel description</CFormLabel>
              <CFormTextarea
                value={editingPanel.description}
                onChange={(event) =>
                  setEditingPanel((current) =>
                    current
                      ? { ...current, description: event.target.value }
                      : current
                  )
                }
                maxLength={2000}
                rows={3}
              />
            </div>

            <div>
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
            </div>

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

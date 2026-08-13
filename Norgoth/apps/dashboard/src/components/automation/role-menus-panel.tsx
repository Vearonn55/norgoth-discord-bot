"use client";

import { useEffect, useMemo, useState } from "react";
import { CFormInput, CFormLabel, CFormSelect, CSpinner } from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DiscordRoleBadge } from "@/components/ui/discord-role-badge";
import { SectionCard } from "@/components/ui/section-card";
import { DataTable } from "@/components/ui/data-table";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { AssignmentMethodSelector } from "@/components/automation/assignment-method-selector";
import { DropdownRoleEditor } from "@/components/automation/dropdown-role-editor";
import { ButtonRoleEditor } from "@/components/automation/button-role-editor";
import { ReactionRoleEditor } from "@/components/automation/reaction-role-editor";
import { RoleAssignmentPreview } from "@/components/automation/role-assignment-preview";
import { EmbedInstanceSelector } from "@/components/automation/embed-instance-selector";
import {
  EmbedDraftCreator,
  type EmbedDraftValue,
} from "@/components/embed-messages/embed-draft-creator";
import { MessageSourceToggle } from "@/components/discord/message-source-toggle";
import { RichMessageEditor } from "@/components/editors/rich-message-editor";
import { validateEmbed } from "@/lib/discord/message-payload";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useParams } from "next/navigation";
import { formatDateTime } from "@/lib/datetime";
import {
  roleMenuInteractionLabel,
  type RoleMenuInteraction,
} from "@/lib/discord/role-menu-modes";
import { roleColorStyles } from "@/lib/discord/role-color";
import {
  newRoleMenu,
  useRoleMenusStore,
  type RoleMenu,
  type RoleMenuEntry,
} from "@/stores/automation-store";
import { useEmbedMessagesStore } from "@/stores/embed-messages-store";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";

const PAGE_SIZE = 6;

export function RoleMenusPanel() {
  const dict = useLocaleDict();
  const d = dict.roleMenusPage;
  const { guildId, resources, loading, error, reload } = useFirstGuild();
  const params = useParams();
  const lang = String(params?.lang || "en");

  const menus = useRoleMenusStore((s) => s.menus);
  const editing = useRoleMenusStore((s) => s.editing);
  const busy = useRoleMenusStore((s) => s.busy);
  const feedback = useRoleMenusStore((s) => s.feedback);
  const feedbackIsError = useRoleMenusStore((s) => s.feedbackIsError);
  const setEditing = useRoleMenusStore((s) => s.setEditing);
  const load = useRoleMenusStore((s) => s.load);
  const saveEditing = useRoleMenusStore((s) => s.saveEditing);
  const publish = useRoleMenusStore((s) => s.publish);
  const deleteMenu = useRoleMenusStore((s) => s.deleteMenu);

  const embedMessages = useEmbedMessagesStore((s) => s.messages);
  const embedsLoading = useEmbedMessagesStore((s) => s.loading);
  const loadEmbeds = useEmbedMessagesStore((s) => s.load);
  const createEmbed = useEmbedMessagesStore((s) => s.create);
  const sendEmbed = useEmbedMessagesStore((s) => s.send);

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [roleSearch, setRoleSearch] = useState("");
  const [pendingDelete, setPendingDelete] = useState<RoleMenu | null>(null);

  // Self-Assignable Roles embed source workflow. `NONE` shows the source
  // chooser; `SELECT_EXISTING` reuses the two-stage instance selector; and
  // `CREATE_NEW` reuses the shared Embed Draft Creator, then publishes it to a
  // channel so role controls have a live Discord message to attach to.
  type SourceMode = "NONE" | "SELECT_EXISTING" | "CREATE_NEW";
  const [sourceMode, setSourceMode] = useState<SourceMode>("NONE");
  // Live values authored in the Create New embed form. Persisted to the central
  // Embed Messages drafts only when the menu is saved.
  const [newEmbedDraft, setNewEmbedDraft] = useState<EmbedDraftValue | null>(
    null
  );
  const [savingDraft, setSavingDraft] = useState(false);
  const [sarError, setSarError] = useState<string | null>(null);
  const [pendingSwitch, setPendingSwitch] = useState<SourceMode | null>(null);
  // Destination channel a newly authored embed is posted to so role controls
  // have a live Discord message to attach to.
  const [newMenuChannelId, setNewMenuChannelId] = useState("");

  useEffect(() => {
    if (!guildId) return;
    void load(guildId);
  }, [guildId, load]);

  useEffect(() => {
    if (!guildId) return;
    void loadEmbeds(guildId);
  }, [guildId, loadEmbeds]);

  const selectedEmbed = useMemo(
    () => embedMessages.find((m) => m.id === editing?.embed_message_id),
    [embedMessages, editing?.embed_message_id]
  );

  const embedBound = Boolean(
    editing?.binding_type === "embed_message" && editing?.embed_message_id
  );
  const previewEmbedLoading = embedBound && embedsLoading && !selectedEmbed;
  const previewEmbedMissing = embedBound && !embedsLoading && !selectedEmbed;

  // In Create New, the side member preview renders the live authored draft; in
  // Select From Draft it renders the persisted selected draft.
  const isCreateNew = sourceMode === "CREATE_NEW";
  const isTextMessage = editing?.message_source === "text";
  const previewEmbed = isTextMessage
    ? null
    : isCreateNew
      ? (newEmbedDraft?.embed ?? null)
      : (selectedEmbed?.embed_json ?? null);
  const previewContent = isTextMessage
    ? editing?.text_content
    : isCreateNew
      ? newEmbedDraft?.content
      : selectedEmbed?.content;
  const previewLoading = isTextMessage
    ? false
    : isCreateNew
      ? false
      : previewEmbedLoading;
  const previewMissing = isTextMessage
    ? false
    : isCreateNew
      ? false
      : previewEmbedMissing;

  const channels = resources?.channels ?? [];
  const roles = (resources?.roles ?? []).filter((role) => !role.managed);
  const guildEmojis = resources?.emojis ?? [];
  const roleById = useMemo(
    () => new Map(roles.map((role) => [role.id, role])),
    [roles]
  );
  const channelNames = new Map(
    channels.map((channel) => [channel.id, channel.name])
  );

  const filteredMenus = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return menus;
    return menus.filter((menu) =>
      [
        menu.title,
        menu.description,
        roleMenuInteractionLabel(menu.interaction),
        ...menu.roles.map((r) => r.label),
      ]
        .join(" ")
        .toLowerCase()
        .includes(q)
    );
  }, [menus, search]);

  const filteredRoles = useMemo(() => {
    const q = roleSearch.trim().toLowerCase();
    return roles.filter((role) =>
      q ? role.name.toLowerCase().includes(q) : true
    );
  }, [roles, roleSearch]);

  const hasNewDraftContent = Boolean(
    newEmbedDraft &&
      (newEmbedDraft.name.trim() ||
        newEmbedDraft.content.trim() ||
        newEmbedDraft.embed?.title ||
        newEmbedDraft.embed?.description)
  );

  function resetSarState() {
    setSourceMode("NONE");
    setNewEmbedDraft(null);
    setSavingDraft(false);
    setSarError(null);
    setPendingSwitch(null);
    setNewMenuChannelId("");
  }

  function applySourceMode(next: SourceMode) {
    setSarError(null);
    if (next !== "CREATE_NEW") {
      setNewEmbedDraft(null);
      setNewMenuChannelId("");
    }
    if (next === "SELECT_EXISTING") {
      setEditing((current) =>
        current ? { ...current, binding_type: "embed_message" } : current
      );
    } else if (next === "CREATE_NEW") {
      // Start a fresh draft: clear any existing binding deliberately.
      setEditing((current) =>
        current
          ? {
              ...current,
              binding_type: "embed_message",
              embed_message_id: null,
              embed_delivery_id: null,
            }
          : current
      );
    }
    setSourceMode(next);
  }

  function requestSourceMode(next: SourceMode) {
    if (sourceMode === next) return;
    // Leaving Create New with unsaved authored content loses that draft.
    if (sourceMode === "CREATE_NEW" && next !== "CREATE_NEW" && hasNewDraftContent) {
      setPendingSwitch(next);
      return;
    }
    applySourceMode(next);
  }

  async function handleSaveMenu() {
    if (!editing || !guildId) return;

    if (editing.message_source === "text") {
      if (!editing.text_content.trim()) {
        setSarError(d.errWriteText);
        return;
      }
      if (!editing.channel_id) {
        setSarError(d.errChooseChannel);
        return;
      }
      const next: RoleMenu = {
        ...editing,
        binding_type: "standalone",
        embed_message_id: null,
        embed_delivery_id: null,
      };
      setEditing(next);
      const { menus, persist } = useRoleMenusStore.getState();
      const exists = menus.some((menu) => menu.id === next.id);
      const nextMenus = exists
        ? menus.map((menu) => (menu.id === next.id ? next : menu))
        : [...menus, next];
      const saved = await persist(guildId, nextMenus);
      if (saved) {
        resetSarState();
        setEditing(null);
      }
      return;
    }

    // For a newly authored embed, persist it to the central drafts, post it to
    // the chosen channel so a live Discord message exists, then bind the menu to
    // that delivery — no separate "Create" or "Publish embed" action needed.
    if (sourceMode === "CREATE_NEW" && !editing.embed_message_id) {
      if (!newEmbedDraft || !newEmbedDraft.name.trim()) {
        setSarError(d.errEmbedName);
        return;
      }
      const embedErrors = validateEmbed(newEmbedDraft.embed);
      if (embedErrors.length > 0) {
        setSarError(embedErrors[0]);
        return;
      }
      if (!newMenuChannelId) {
        setSarError(d.errChooseChannel);
        return;
      }

      setSavingDraft(true);
      setSarError(null);
      const created = await createEmbed(guildId, {
        name: newEmbedDraft.name.trim(),
        description: newEmbedDraft.description.trim(),
        content: newEmbedDraft.content,
        embed_json: newEmbedDraft.embed,
      });

      if (!created) {
        setSavingDraft(false);
        setSarError(
          useEmbedMessagesStore.getState().error ??
            d.errSaveDraft
        );
        return;
      }

      // Post the draft to the chosen channel to create the live delivery the
      // role controls will attach to on publish.
      const delivered = await sendEmbed(guildId, created.id, newMenuChannelId);
      setSavingDraft(false);

      const delivery = delivered?.deliveries.find(
        (d) => d.channel_id === newMenuChannelId && d.discord_message_id
      );
      if (!delivery) {
        setSarError(d.errPostEmbed);
        return;
      }

      setEditing((current) =>
        current
          ? {
              ...current,
              binding_type: "embed_message",
              embed_message_id: created.id,
              embed_delivery_id: delivery.id,
              channel_id: delivery.channel_id,
            }
          : current
      );
    }

    await saveEditing(guildId);
  }

  function updateEntry(roleId: string, patch: Partial<RoleMenuEntry>) {
    setEditing((current) => {
      if (!current) return current;
      return {
        ...current,
        roles: current.roles.map((entry) =>
          entry.role_id === roleId ? { ...entry, ...patch } : entry
        ),
      };
    });
  }

  function removeEntry(roleId: string) {
    setEditing((current) => {
      if (!current) return current;
      return {
        ...current,
        roles: current.roles.filter((entry) => entry.role_id !== roleId),
      };
    });
  }

  if (loading) {
    return (
      <Card>
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          {d.loading}
        </div>
      </Card>
    );
  }

  if (error || !guildId) {
    return (
      <Card>
        <div className="d-flex flex-column gap-3">
          <Badge variant="warning">{d.botRequired}</Badge>
          <p className="small text-body-secondary">{error}</p>
          <Button variant="secondary" onClick={() => void reload()}>
            {d.retry}
          </Button>
        </div>
      </Card>
    );
  }

  const interaction = (editing?.interaction ??
    "buttons") as RoleMenuInteraction;

  return (
    <div className="d-flex flex-column gap-3">
      <SectionCard level="primary" category="roles">
        <div className="d-flex flex-wrap align-items-center justify-content-between gap-3">
          <div>
            <h2 className="h5 mb-0 fw-semibold">{d.title}</h2>
            <p className="mt-1 mb-0 small text-body-secondary">
              {formatDict(d.subtitle, { count: menus.length })}
            </p>
          </div>
          {feedback ? (
            <span
              className={`small ${
                feedbackIsError ? "text-danger" : "text-success"
              }`}
            >
              {feedback}
            </span>
          ) : null}
        </div>
      </SectionCard>

      <FeatureConfigurationModal
        visible={editing !== null}
        title={
          editing && menus.some((menu) => menu.id === editing.id)
            ? d.editMenu
            : d.newMenu
        }
        category="roles"
        size="xl"
        saving={busy || savingDraft}
        error={feedbackIsError ? feedback : sarError}
        saveDisabled={
          !editing ||
          editing.roles.length === 0 ||
          (editing.message_source === "text"
            ? !editing.text_content.trim() || !editing.channel_id
            : sourceMode === "NONE" ||
              (sourceMode === "SELECT_EXISTING" && !editing.embed_delivery_id) ||
              (sourceMode === "CREATE_NEW" &&
                (!newEmbedDraft ||
                  !newEmbedDraft.name.trim() ||
                  !newMenuChannelId ||
                  validateEmbed(newEmbedDraft.embed).length > 0)))
        }
        saveLabel={d.saveMenu}
        onClose={() => {
          setEditing(null);
          resetSarState();
        }}
        onSave={() => void handleSaveMenu()}
      >
        {editing ? (
          <div className="d-flex flex-column gap-4">
            <div className="row g-3">
              <div className="col-lg-7 d-flex flex-column gap-3">
                <div className="d-flex align-items-center justify-content-between gap-2">
                  <CFormLabel className="mb-0 fw-medium">
                    {d.menuMessage}
                  </CFormLabel>
                  <MessageSourceToggle
                    value={editing.message_source}
                    onChange={(next) => {
                      setEditing((current) =>
                        current
                          ? {
                              ...current,
                              message_source: next,
                              binding_type:
                                next === "text"
                                  ? "standalone"
                                  : "embed_message",
                            }
                          : current
                      );
                      if (next === "embed") {
                        setSourceMode(
                          editing.embed_delivery_id
                            ? "SELECT_EXISTING"
                            : "NONE"
                        );
                      } else {
                        setSourceMode("NONE");
                      }
                    }}
                  />
                </div>

                {editing.message_source === "text" ? (
                  <>
                    <RichMessageEditor
                      key={`role-menu-text-${editing.id}`}
                      value={editing.text_content}
                      onChange={(markdown) =>
                        setEditing((current) =>
                          current
                            ? { ...current, text_content: markdown }
                            : current
                        )
                      }
                      height={160}
                      placeholder={d.textPlaceholder}
                    />
                    <div>
                      <CFormLabel className="fw-medium">
                        {d.postToChannel}
                      </CFormLabel>
                      <CFormSelect
                        value={editing.channel_id ?? ""}
                        onChange={(e) =>
                          setEditing((current) =>
                            current
                              ? {
                                  ...current,
                                  channel_id: e.target.value || null,
                                }
                              : current
                          )
                        }
                      >
                        <option value="">{d.selectChannel}</option>
                        {channels.map((channel) => (
                          <option key={channel.id} value={channel.id}>
                            #{channel.name}
                          </option>
                        ))}
                      </CFormSelect>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="d-flex gap-2">
                      <Button
                        variant={
                          sourceMode === "SELECT_EXISTING"
                            ? "primary"
                            : "secondary"
                        }
                        onClick={() => requestSourceMode("SELECT_EXISTING")}
                      >
                        {d.selectFromDraft}
                      </Button>
                      <Button
                        variant={
                          sourceMode === "CREATE_NEW" ? "primary" : "secondary"
                        }
                        onClick={() => requestSourceMode("CREATE_NEW")}
                      >
                        {d.createNew}
                      </Button>
                    </div>

                    {sourceMode === "NONE" ? (
                      <p className="small text-body-secondary mb-0">
                        {d.chooseEmbedSource}
                      </p>
                    ) : null}

                    {sourceMode === "SELECT_EXISTING" ? (
                      <EmbedInstanceSelector
                        guildId={guildId}
                        channelNames={channelNames}
                        embedMessageId={editing.embed_message_id}
                        embedDeliveryId={editing.embed_delivery_id}
                        onChange={(
                          embedMessageId,
                          embedDeliveryId,
                          channelId
                        ) =>
                          setEditing((current) =>
                            current
                              ? {
                                  ...current,
                                  binding_type: "embed_message",
                                  message_source: "embed",
                                  embed_message_id: embedMessageId,
                                  embed_delivery_id: embedDeliveryId,
                                  channel_id: channelId ?? current.channel_id,
                                }
                              : current
                          )
                        }
                      />
                    ) : null}

                    {sourceMode === "CREATE_NEW" ? (
                      <>
                        <EmbedDraftCreator
                          guildId={guildId}
                          channels={channels}
                          mode="create"
                          compact
                          hidePreview
                          hideActions
                          onDraftChange={setNewEmbedDraft}
                        />
                        <div>
                          <CFormLabel className="fw-medium">
                            {d.postToChannel}
                          </CFormLabel>
                          <CFormSelect
                            value={newMenuChannelId}
                            onChange={(e) =>
                              setNewMenuChannelId(e.target.value)
                            }
                          >
                            <option value="">{d.selectChannel}</option>
                            {channels.map((channel) => (
                              <option key={channel.id} value={channel.id}>
                                #{channel.name}
                              </option>
                            ))}
                          </CFormSelect>
                          <p className="small text-body-secondary mt-1 mb-0">
                            {d.postEmbedHelp}
                          </p>
                        </div>
                      </>
                    ) : null}
                  </>
                )}

                {sarError ? (
                  <p className="small text-danger mb-0">{sarError}</p>
                ) : null}

                <AssignmentMethodSelector
                  value={interaction}
                  onChange={(next) =>
                    setEditing((current) =>
                      current ? { ...current, interaction: next } : current
                    )
                  }
                />

                <div>
                  <div className="mb-2 fw-medium">
                    {formatDict(d.rolesInMenu, { count: editing.roles.length })}
                  </div>
                  <CFormInput
                    className="mb-2"
                    value={roleSearch}
                    onChange={(e) => setRoleSearch(e.target.value)}
                    placeholder={d.searchRoles}
                  />
                  <div className="d-flex flex-wrap gap-2">
                    {filteredRoles.slice(0, 40).map((role) => {
                      const isSelected = editing.roles.some(
                        (entry) => entry.role_id === role.id
                      );
                      const tint = roleColorStyles(role.color);
                      return (
                        <button
                          key={role.id}
                          type="button"
                          onClick={() =>
                            setEditing((current) => {
                              if (!current) return current;
                              if (isSelected) {
                                return {
                                  ...current,
                                  roles: current.roles.filter(
                                    (entry) => entry.role_id !== role.id
                                  ),
                                };
                              }
                              if (current.roles.length >= 25) return current;
                              return {
                                ...current,
                                roles: [
                                  ...current.roles,
                                  {
                                    role_id: role.id,
                                    label: role.name,
                                    mode: "toggle",
                                    style: "secondary",
                                    emoji: "",
                                  },
                                ],
                              };
                            })
                          }
                          className={[
                            "btn btn-sm",
                            isSelected
                              ? "btn-primary"
                              : "btn-outline-secondary",
                          ].join(" ")}
                          style={
                            tint && !isSelected
                              ? {
                                  borderColor: tint.borderColor,
                                  background: tint.background,
                                }
                              : undefined
                          }
                        >
                          <DiscordRoleBadge
                            name={role.name}
                            color={role.color}
                          />
                        </button>
                      );
                    })}
                  </div>
                </div>

                {interaction === "select" ? (
                  <DropdownRoleEditor
                    entries={editing.roles}
                    rolesById={roleById}
                    guildEmojis={guildEmojis}
                    onUpdate={updateEntry}
                    onRemove={removeEntry}
                  />
                ) : null}

                {interaction === "buttons" ? (
                  <ButtonRoleEditor
                    entries={editing.roles}
                    rolesById={roleById}
                    guildEmojis={guildEmojis}
                    onUpdate={updateEntry}
                    onRemove={removeEntry}
                  />
                ) : null}

                {interaction === "reactions" ? (
                  <ReactionRoleEditor
                    entries={editing.roles}
                    rolesById={roleById}
                    guildEmojis={guildEmojis}
                    onUpdate={updateEntry}
                    onRemove={removeEntry}
                  />
                ) : null}

                {editing.roles.length === 0 ? (
                  <p className="small text-warning mb-0">
                    {d.noRolesWarning}
                  </p>
                ) : null}
              </div>

              <div className="col-lg-5">
                <RoleAssignmentPreview
                  menu={editing}
                  embed={previewEmbed}
                  content={previewContent}
                  embedLoading={previewLoading}
                  embedMissing={previewMissing}
                />
              </div>
            </div>
          </div>
        ) : null}
      </FeatureConfigurationModal>

      <Card>
        <DataTable
          columns={[
            {
              key: "name",
              header: d.colMenuName,
              cell: (menu: RoleMenu) => {
                const draft =
                  menu.binding_type === "embed_message" && menu.embed_message_id
                    ? embedMessages.find((m) => m.id === menu.embed_message_id)
                    : undefined;
                const draftMissing =
                  menu.binding_type === "embed_message" &&
                  Boolean(menu.embed_message_id) &&
                  !embedsLoading &&
                  !draft;
                const label =
                  menu.binding_type === "embed_message"
                    ? menu.embed_message_id
                      ? draft
                        ? formatDict(d.boundMenu, { name: draft.name })
                        : embedsLoading
                          ? d.loadingShort
                          : d.embedDraftMissing
                      : menu.title || d.embedBoundMenu
                    : menu.title || d.untitledMenu;
                return (
                  <div className="d-flex flex-column">
                    <span
                      className={`fw-semibold ${draftMissing ? "text-danger" : ""}`}
                    >
                      {label}
                    </span>
                    <span className="small text-body-secondary text-truncate">
                      {menu.binding_type === "embed_message"
                        ? d.boundToEmbed
                        : menu.description || d.standaloneEmbed}
                    </span>
                  </div>
                );
              },
            },
            {
              key: "interaction",
              header: d.colAssignmentUi,
              cell: (menu: RoleMenu) => (
                <Badge variant="neutral">
                  {menu.interaction === "select"
                      ? d.interactionSelect
                      : menu.interaction === "reactions"
                        ? d.interactionReactions
                        : d.interactionButtons}
                </Badge>
              ),
            },
            {
              key: "roles",
              header: d.colRoles,
              cell: (menu: RoleMenu) => (
                <span>
                  {formatDict(
                    menu.roles.length === 1 ? d.roleCountOne : d.roleCountMany,
                    { count: menu.roles.length },
                  )}
                </span>
              ),
            },
            {
              key: "status",
              header: d.colStatus,
              cell: (menu: RoleMenu) => (
                <div className="d-flex flex-wrap gap-1">
                  {menu.message_id ? (
                    <Badge variant="success">{d.published}</Badge>
                  ) : (
                    <Badge variant="neutral">{d.draft}</Badge>
                  )}
                  {menu.channel_id ? (
                    <Badge variant="info">
                      #{channelNames.get(menu.channel_id) ?? menu.channel_id}
                    </Badge>
                  ) : null}
                  <BindingHealthBadge health={menu.binding_health} />
                </div>
              ),
            },
            {
              key: "updated",
              header: d.colUpdated,
              cell: (menu: RoleMenu) => (
                <span className="small text-body-secondary">
                  {formatDateTime(menu.published_at, lang)}
                </span>
              ),
            },
            {
              key: "actions",
              header: "",
              className: "text-end",
              cell: (menu: RoleMenu) => (
                <div className="d-flex justify-content-end gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setEditing({
                        ...menu,
                        interaction: menu.interaction ?? "buttons",
                        roles: menu.roles.map((r) => ({
                          ...r,
                          mode: r.mode ?? "toggle",
                          style: r.style ?? "secondary",
                          emoji: r.emoji ?? "",
                        })),
                      });
                      setNewEmbedDraft(null);
                      setNewMenuChannelId("");
                      setSarError(null);
                      setPendingSwitch(null);
                      setSourceMode(
                        menu.message_source === "embed" &&
                          menu.binding_type === "embed_message" &&
                          menu.embed_message_id
                          ? "SELECT_EXISTING"
                          : "NONE"
                      );
                    }}
                    disabled={editing !== null}
                  >
                    {d.edit}
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => void publish(guildId, menu)}
                    disabled={
                      busy ||
                      menu.roles.length === 0 ||
                      (menu.binding_type === "embed_message"
                        ? !menu.embed_delivery_id
                        : !menu.channel_id)
                    }
                  >
                    {d.publish}
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => setPendingDelete(menu)}
                    disabled={busy}
                  >
                    {d.delete}
                  </Button>
                </div>
              ),
            },
          ]}
          rows={filteredMenus}
          rowKey={(menu) => menu.id}
          emptyMessage={d.emptyMenus}
          search={search}
          onSearchChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
          searchPlaceholder={d.searchMenus}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={setPage}
          toolbar={
            <Button
              variant="primary"
              onClick={() => {
                setEditing(newRoleMenu());
                resetSarState();
              }}
              disabled={editing !== null}
            >
              {d.newMenu}
            </Button>
          }
        />
      </Card>

      <ConfirmDialog
        visible={pendingDelete !== null}
        title={d.deleteTitle}
        message={
          <p className="mb-0 text-body-secondary">
            {pendingDelete
              ? formatDict(
                  pendingDelete.message_id
                    ? pendingDelete.binding_type === "embed_message"
                      ? d.deleteEmbedBound
                      : d.deleteStandalonePublished
                    : d.deleteDraftOnly,
                  {
                    name: pendingDelete.title || d.deleteThisMenu,
                  },
                )
              : ""}
          </p>
        }
        confirmLabel={d.deleteConfirm}
        destructive
        busy={busy}
        onConfirm={async () => {
          if (!pendingDelete) return;
          const ok = await deleteMenu(guildId, pendingDelete);
          if (ok) setPendingDelete(null);
        }}
        onCancel={() => setPendingDelete(null)}
      />

      <ConfirmDialog
        visible={pendingSwitch !== null}
        title={d.discardTitle}
        message={
          <p className="mb-0 text-body-secondary">
            {d.discardMessage}
          </p>
        }
        confirmLabel={d.discardConfirm}
        destructive
        onConfirm={() => {
          const next = pendingSwitch;
          setPendingSwitch(null);
          if (next) applySourceMode(next);
        }}
        onCancel={() => setPendingSwitch(null)}
      />
    </div>
  );
}

function BindingHealthBadge({
  health,
}: {
  health: RoleMenu["binding_health"];
}) {
  const dict = useLocaleDict();
  const d = dict.roleMenusPage;
  switch (health) {
    case "healthy":
      return <Badge variant="success">{d.healthHealthy}</Badge>;
    case "needs_resync":
      return <Badge variant="warning">{d.healthNeedsResync}</Badge>;
    case "message_missing":
      return <Badge variant="warning">{d.healthMessageMissing}</Badge>;
    case "needs_reassignment":
      return <Badge variant="danger">{d.healthNeedsReassignment}</Badge>;
    case "unbound":
      return <Badge variant="warning">{d.healthUnbound}</Badge>;
    default:
      return null;
  }
}

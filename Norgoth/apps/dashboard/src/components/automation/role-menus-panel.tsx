"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CFormInput,
  CFormLabel,
  CFormSelect,
  CSpinner,
} from "@coreui/react";
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
import { useFirstGuild } from "@/lib/use-first-guild";
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

const PAGE_SIZE = 6;

export function RoleMenusPanel() {
  const { guildId, resources, loading, error, reload } = useFirstGuild();

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

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [roleSearch, setRoleSearch] = useState("");
  const [pendingDelete, setPendingDelete] = useState<RoleMenu | null>(null);

  useEffect(() => {
    if (!guildId) return;
    void load(guildId);
  }, [guildId, load]);

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
          Loading role menus…
        </div>
      </Card>
    );
  }

  if (error || !guildId) {
    return (
      <Card>
        <div className="d-flex flex-column gap-3">
          <Badge variant="warning">Bot required</Badge>
          <p className="small text-body-secondary">{error}</p>
          <Button variant="secondary" onClick={() => void reload()}>
            Retry
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
            <h2 className="h5 mb-0 fw-semibold">Self-Assignable Roles</h2>
            <p className="mt-1 mb-0 small text-body-secondary">
              Dropdown List, Button, or Emoji Reaction · {menus.length} menus
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
            ? "Edit Menu"
            : "New Menu"
        }
        category="roles"
        size="xl"
        saving={busy}
        error={feedbackIsError ? feedback : null}
        saveDisabled={!editing || editing.roles.length === 0}
        saveLabel="Save Menu"
        onClose={() => setEditing(null)}
        onSave={() => void saveEditing(guildId)}
      >
        {editing ? (
          <div className="d-flex flex-column gap-4">
            <div className="row g-3">
              <div className="col-lg-7 d-flex flex-column gap-3">
                <div>
                  <CFormLabel>Title</CFormLabel>
                  <CFormInput
                    value={editing.title}
                    onChange={(event) =>
                      setEditing((current) =>
                        current
                          ? { ...current, title: event.target.value }
                          : current
                      )
                    }
                    maxLength={256}
                  />
                </div>

                <div>
                  <CFormLabel>Target channel</CFormLabel>
                  <CFormSelect
                    value={editing.channel_id ?? ""}
                    onChange={(event) =>
                      setEditing((current) =>
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
                </div>

                <div>
                  <CFormLabel>Description</CFormLabel>
                  <CFormInput
                    value={editing.description}
                    onChange={(event) =>
                      setEditing((current) =>
                        current
                          ? { ...current, description: event.target.value }
                          : current
                      )
                    }
                    maxLength={2000}
                  />
                </div>

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
                    Roles in this menu ({editing.roles.length} / 25)
                  </div>
                  <CFormInput
                    className="mb-2"
                    value={roleSearch}
                    onChange={(e) => setRoleSearch(e.target.value)}
                    placeholder="Search roles to add…"
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
                    This menu has no roles. Add at least one role before
                    publishing.
                  </p>
                ) : null}
              </div>

              <div className="col-lg-5">
                <RoleAssignmentPreview menu={editing} />
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
              header: "Menu Name",
              cell: (menu: RoleMenu) => (
                <div className="d-flex flex-column">
                  <span className="fw-semibold">{menu.title}</span>
                  {menu.description ? (
                    <span className="small text-body-secondary text-truncate">
                      {menu.description}
                    </span>
                  ) : null}
                </div>
              ),
            },
            {
              key: "interaction",
              header: "Assignment UI",
              cell: (menu: RoleMenu) => (
                <Badge variant="neutral">
                  {roleMenuInteractionLabel(menu.interaction)}
                </Badge>
              ),
            },
            {
              key: "roles",
              header: "Roles",
              cell: (menu: RoleMenu) => (
                <span>
                  {menu.roles.length} role{menu.roles.length === 1 ? "" : "s"}
                </span>
              ),
            },
            {
              key: "status",
              header: "Status",
              cell: (menu: RoleMenu) => (
                <div className="d-flex flex-wrap gap-1">
                  {menu.message_id ? (
                    <Badge variant="success">Published</Badge>
                  ) : (
                    <Badge variant="neutral">Draft</Badge>
                  )}
                  {menu.channel_id ? (
                    <Badge variant="info">
                      #{channelNames.get(menu.channel_id) ?? menu.channel_id}
                    </Badge>
                  ) : (
                    <Badge variant="warning">No channel</Badge>
                  )}
                </div>
              ),
            },
            {
              key: "updated",
              header: "Updated",
              cell: (menu: RoleMenu) => (
                <span className="small text-body-secondary">
                  {menu.published_at
                    ? new Date(menu.published_at).toLocaleString()
                    : "—"}
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
                    onClick={() =>
                      setEditing({
                        ...menu,
                        interaction: menu.interaction ?? "buttons",
                        roles: menu.roles.map((r) => ({
                          ...r,
                          mode: r.mode ?? "toggle",
                          style: r.style ?? "secondary",
                          emoji: r.emoji ?? "",
                        })),
                      })
                    }
                    disabled={editing !== null}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => void publish(guildId, menu)}
                    disabled={
                      busy || !menu.channel_id || menu.roles.length === 0
                    }
                  >
                    Publish
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => setPendingDelete(menu)}
                    disabled={busy}
                  >
                    Delete
                  </Button>
                </div>
              ),
            },
          ]}
          rows={filteredMenus}
          rowKey={(menu) => menu.id}
          emptyMessage="No role menus yet. Create one and publish it to a channel so members can self-assign roles."
          search={search}
          onSearchChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
          searchPlaceholder="Search menus…"
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={setPage}
          toolbar={
            <Button
              variant="primary"
              onClick={() => setEditing(newRoleMenu())}
              disabled={editing !== null}
            >
              New Menu
            </Button>
          }
        />
      </Card>

      <ConfirmDialog
        visible={pendingDelete !== null}
        title="Delete Role Menu?"
        message={
          <p className="mb-0 text-body-secondary">
            This deletes <strong>{pendingDelete?.title}</strong>
            {pendingDelete?.message_id
              ? ", including the message already published to Discord (its buttons, dropdown, or reactions)."
              : "."}{" "}
            This cannot be undone.
          </p>
        }
        confirmLabel="Delete Menu"
        destructive
        busy={busy}
        onConfirm={async () => {
          if (!pendingDelete) return;
          const ok = await deleteMenu(guildId, pendingDelete);
          if (ok) setPendingDelete(null);
        }}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CAlert,
  CCol,
  CFormInput,
  CFormLabel,
  CFormSelect,
  CRow,
  CSpinner,
} from "@coreui/react";
import { cilBan, cilLink, cilShieldAlt, cilSpeedometer } from "@coreui/icons";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { NumberInput } from "@/components/ui/number-input";
import { DataTable } from "@/components/ui/data-table";
import { MiniFeatureCard } from "@/components/ui/mini-feature-card";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/layout/page-header";
import { PageActionFooter } from "@/components/layout/page-action-footer";
import { MutedSection } from "@/components/ui/feature-muting";
import {
  FeatureConfigurationModal,
} from "@/components/ui/feature-modal";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";
import { useFirstGuild } from "@/lib/use-first-guild";
import {
  useAutomodStore,
  type AutomodAction,
} from "@/stores/automod-store";

type AutomodFeature = "words" | "spam" | "invites" | "exemptions";

export function AutomodPanel() {
  const dict = useLocaleDict();
  const d = dict.autoModPage;
  const { guildId, resources, loading, error, reload } = useFirstGuild();

  const config = useAutomodStore((s) => s.config);
  const savedSnapshot = useAutomodStore((s) => s.savedSnapshot);
  const wordInput = useAutomodStore((s) => s.wordInput);
  const wordSearch = useAutomodStore((s) => s.wordSearch);
  const wordPage = useAutomodStore((s) => s.wordPage);
  const saving = useAutomodStore((s) => s.saving);
  const saveError = useAutomodStore((s) => s.saveError);
  const savedAt = useAutomodStore((s) => s.savedAt);
  const setConfig = useAutomodStore((s) => s.setConfig);
  const setWordInput = useAutomodStore((s) => s.setWordInput);
  const setWordSearch = useAutomodStore((s) => s.setWordSearch);
  const setWordPage = useAutomodStore((s) => s.setWordPage);
  const loadConfig = useAutomodStore((s) => s.load);
  const saveStore = useAutomodStore((s) => s.save);
  const addWord = useAutomodStore((s) => s.addWord);
  const removeWord = useAutomodStore((s) => s.removeWord);

  const dirty = JSON.stringify(config) !== savedSnapshot;
  const [activeModal, setActiveModal] = useState<AutomodFeature | null>(null);

  const actionOptions: { value: AutomodAction; label: string }[] = [
    { value: "delete", label: d.actionDelete },
    { value: "warn", label: d.actionWarn },
    { value: "timeout", label: d.actionTimeout },
  ];

  const actionLabels: Record<AutomodAction, string> = {
    delete: d.actionLabelDelete,
    warn: d.actionLabelWarn,
    timeout: d.actionLabelTimeout,
  };

  useEffect(() => {
    if (!guildId) return;
    void loadConfig(guildId);
  }, [guildId, loadConfig]);

  async function save() {
    if (!guildId) return;
    await saveStore(guildId);
  }

  // The master switch is authoritative and persists immediately, so the
  // disabled state can be saved even though the page-level Save is disabled
  // while the feature is off.
  async function setEnabledAndSave(checked: boolean) {
    if (!guildId) return;
    setConfig((current) => ({ ...current, enabled: checked }));
    await saveStore(guildId);
  }

  async function handleModalSave() {
    if (!guildId) return;
    await saveStore(guildId);
    if (!useAutomodStore.getState().saveError) setActiveModal(null);
  }

  function toggleId(list: "exempt_channel_ids" | "exempt_role_ids", id: string) {
    setConfig((current) => {
      const values = current[list];
      return {
        ...current,
        [list]: values.includes(id)
          ? values.filter((item) => item !== id)
          : [...values, id],
      };
    });
  }

  const filteredWords = useMemo(() => {
    const query = wordSearch.trim().toLowerCase();
    const words = config.prohibited_words;
    if (!query) return words.map((word) => ({ word }));
    return words
      .filter((word) => word.includes(query))
      .map((word) => ({ word }));
  }, [config.prohibited_words, wordSearch]);

  if (loading) {
    return (
      <Card>
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          <span>{d.loading}</span>
        </div>
      </Card>
    );
  }

  if (error || !guildId) {
    return (
      <Card>
        <div className="d-flex flex-column gap-3">
          <Badge variant="warning">{d.botRequired}</Badge>
          <p className="mb-0 text-body-secondary">{error}</p>
          <Button variant="secondary" onClick={() => void reload()}>
            {d.retry}
          </Button>
        </div>
      </Card>
    );
  }

  const channels = resources?.channels ?? [];
  const roles = (resources?.roles ?? []).filter((role) => !role.managed);
  const showEmptyRulesBanner =
    config.enabled &&
    config.prohibited_words.length === 0 &&
    !config.block_invites;

  const wordCount = config.prohibited_words.length;
  const spamOn = config.spam_enabled || config.duplicate_enabled;
  const invitesOn = config.block_invites || config.mass_mention_enabled;
  const exemptionsSet =
    config.exempt_channel_ids.length > 0 ||
    config.exempt_role_ids.length > 0 ||
    config.exempt_manage_messages;

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={d.title}
        icon={<Icon icon={cilBan} size="xl" />}
        category="moderation"
        description={d.description}
        infoKey="autoModeration"
        masterToggle={{
          enabled: config.enabled,
          onChange: (checked) => void setEnabledAndSave(checked),
          loading: saving,
        }}
      />

      {dirty && config.enabled ? (
        <CAlert color="warning" className="mb-0">
          {d.unsavedChanges}
        </CAlert>
      ) : null}

      {showEmptyRulesBanner ? (
        <CAlert color="info" className="mb-0">
          {d.emptyRulesBanner}
        </CAlert>
      ) : null}

      <MutedSection
        enabled={config.enabled}
        className="d-flex flex-column gap-4"
      >
        <Card>
          <div>
            <CFormLabel className="mb-2">{d.scopeLabel}</CFormLabel>
            <div className="row row-cols-1 row-cols-md-3 g-2">
              <div className="col">
                <ToggleLine
                  label={d.scopeText}
                  checked={config.moderation_scope.text}
                  onChange={(checked) =>
                    setConfig((current) => ({
                      ...current,
                      moderation_scope: {
                        ...current.moderation_scope,
                        text: checked,
                      },
                    }))
                  }
                />
              </div>
              <div className="col">
                <ToggleLine
                  label={d.scopeThreads}
                  checked={config.moderation_scope.threads}
                  onChange={(checked) =>
                    setConfig((current) => ({
                      ...current,
                      moderation_scope: {
                        ...current.moderation_scope,
                        threads: checked,
                      },
                    }))
                  }
                />
              </div>
              <div className="col">
                <ToggleLine
                  label={d.scopeVoiceText}
                  checked={config.moderation_scope.voice_text}
                  onChange={(checked) =>
                    setConfig((current) => ({
                      ...current,
                      moderation_scope: {
                        ...current.moderation_scope,
                        voice_text: checked,
                      },
                    }))
                  }
                />
              </div>
            </div>
          </div>
        </Card>

        <div className="row row-cols-1 row-cols-md-2 g-3">
          <div className="col">
            <MiniFeatureCard
              icon={cilBan}
              name={d.wordsTitle}
              description={formatDict(d.wordsCardDesc, {
                count: wordCount,
                plural: wordCount === 1 ? d.wordsCardDescOne : d.wordsCardDescMany,
                action: actionLabels[config.word_action],
              })}
              category="moderation"
              enabled={config.words_enabled}
              onToggle={(checked) =>
                setConfig((current) => ({ ...current, words_enabled: checked }))
              }
              onClick={() => setActiveModal("words")}
            />
          </div>
          <div className="col">
            <MiniFeatureCard
              icon={cilSpeedometer}
              name={d.spamTitle}
              description={d.spamCardDesc}
              category="moderation"
              enabled={spamOn}
              onToggle={(checked) =>
                setConfig((current) =>
                  checked
                    ? { ...current, spam_enabled: true }
                    : {
                        ...current,
                        spam_enabled: false,
                        duplicate_enabled: false,
                      }
                )
              }
              onClick={() => setActiveModal("spam")}
            />
          </div>
          <div className="col">
            <MiniFeatureCard
              icon={cilLink}
              name={d.invitesTitle}
              description={d.invitesCardDesc}
              category="moderation"
              enabled={invitesOn}
              onToggle={(checked) =>
                setConfig((current) =>
                  checked
                    ? { ...current, block_invites: true }
                    : {
                        ...current,
                        block_invites: false,
                        mass_mention_enabled: false,
                      }
                )
              }
              onClick={() => setActiveModal("invites")}
            />
          </div>
          <div className="col">
            <MiniFeatureCard
              icon={cilShieldAlt}
              name={d.exemptionsTitle}
              description={d.exemptionsCardDesc}
              category="moderation"
              enabled={config.exempt_manage_messages}
              onToggle={(checked) =>
                setConfig((current) => ({
                  ...current,
                  exempt_manage_messages: checked,
                }))
              }
              status={exemptionsSet ? "configured" : "neutral"}
              onClick={() => setActiveModal("exemptions")}
            />
          </div>
        </div>
      </MutedSection>

      <PageActionFooter
        status={
          <>
            {savedAt ? (
              <span className="small text-success">
                {formatDict(d.savedAt, { time: savedAt })}
              </span>
            ) : null}
            {saveError ? (
              <CAlert color="danger" className="mb-0 py-2">
                {saveError}
              </CAlert>
            ) : null}
          </>
        }
      >
        <Button
          variant="primary"
          onClick={() => void save()}
          disabled={saving || !config.enabled || !dirty}
        >
          {saving ? d.saving : d.saveSettings}
        </Button>
      </PageActionFooter>

      <FeatureConfigurationModal
        visible={activeModal === "words"}
        title={d.wordsTitle}
        description={d.wordsDescModal}
        category="moderation"
        icon={cilBan}
        saving={saving}
        error={saveError}
        onClose={() => setActiveModal(null)}
        onSave={handleModalSave}
      >
        <div className="d-flex flex-column gap-3">
          <div className="d-flex gap-2">
            <CFormInput
              value={wordInput}
              onChange={(event) => setWordInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  addWord();
                }
              }}
              placeholder={d.addWordPlaceholder}
            />
            <Button variant="secondary" onClick={addWord}>
              {d.add}
            </Button>
          </div>

          <DataTable
            columns={[
              {
                key: "word",
                header: d.wordColumn,
                cell: (row) => <code>{row.word}</code>,
              },
              {
                key: "actions",
                header: "",
                className: "w-28 text-end",
                cell: (row) => (
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => removeWord(row.word)}
                  >
                    {d.remove}
                  </Button>
                ),
              },
            ]}
            rows={filteredWords}
            rowKey={(row) => row.word}
            emptyMessage={d.emptyWords}
            search={wordSearch}
            onSearchChange={setWordSearch}
            searchPlaceholder={d.searchWords}
            page={wordPage}
            pageSize={10}
            onPageChange={setWordPage}
          />

          <ActionSelect
            label={d.actionWords}
            value={config.word_action}
            options={actionOptions}
            onChange={(value) =>
              setConfig((current) => ({ ...current, word_action: value }))
            }
          />
        </div>
      </FeatureConfigurationModal>

      <FeatureConfigurationModal
        visible={activeModal === "spam"}
        title={d.spamTitle}
        description={d.spamModalDesc}
        category="moderation"
        icon={cilSpeedometer}
        saving={saving}
        error={saveError}
        onClose={() => setActiveModal(null)}
        onSave={handleModalSave}
      >
        <div className="d-flex flex-column gap-3">
          <ToggleLine
            label={d.messageRateLimit}
            checked={config.spam_enabled}
            onChange={(checked) =>
              setConfig((current) => ({ ...current, spam_enabled: checked }))
            }
          />

          {config.spam_enabled ? (
            <CRow className="g-3">
              <CCol md={6}>
                <NumberField
                  label={d.maxMessages}
                  value={config.spam_max_messages}
                  min={2}
                  max={30}
                  onChange={(value) =>
                    setConfig((current) => ({
                      ...current,
                      spam_max_messages: value,
                    }))
                  }
                />
              </CCol>
              <CCol md={6}>
                <NumberField
                  label={d.withinSeconds}
                  value={config.spam_interval_seconds}
                  min={2}
                  max={120}
                  onChange={(value) =>
                    setConfig((current) => ({
                      ...current,
                      spam_interval_seconds: value,
                    }))
                  }
                />
              </CCol>
            </CRow>
          ) : null}

          <ToggleLine
            label={d.repeatedContent}
            checked={config.duplicate_enabled}
            onChange={(checked) =>
              setConfig((current) => ({
                ...current,
                duplicate_enabled: checked,
              }))
            }
          />

          {config.duplicate_enabled ? (
            <NumberField
              label={d.identicalMessages}
              value={config.duplicate_threshold}
              min={2}
              max={10}
              onChange={(value) =>
                setConfig((current) => ({
                  ...current,
                  duplicate_threshold: value,
                }))
              }
            />
          ) : null}

          <ActionSelect
            label={d.actionSpam}
            value={config.spam_action}
            options={actionOptions}
            onChange={(value) =>
              setConfig((current) => ({ ...current, spam_action: value }))
            }
          />
        </div>
      </FeatureConfigurationModal>

      <FeatureConfigurationModal
        visible={activeModal === "invites"}
        title={d.invitesTitle}
        category="moderation"
        icon={cilLink}
        saving={saving}
        error={saveError}
        onClose={() => setActiveModal(null)}
        onSave={handleModalSave}
      >
        <div className="d-flex flex-column gap-3">
          <ToggleLine
            label={d.blockInvites}
            checked={config.block_invites}
            onChange={(checked) =>
              setConfig((current) => ({ ...current, block_invites: checked }))
            }
          />

          {config.block_invites ? (
            <ActionSelect
              label={d.actionInvites}
              value={config.invite_action}
              options={actionOptions}
              onChange={(value) =>
                setConfig((current) => ({ ...current, invite_action: value }))
              }
            />
          ) : null}

          <ToggleLine
            label={d.blockMassMentions}
            checked={config.mass_mention_enabled}
            onChange={(checked) =>
              setConfig((current) => ({
                ...current,
                mass_mention_enabled: checked,
              }))
            }
          />

          {config.mass_mention_enabled ? (
            <>
              <NumberField
                label={d.mentionThreshold}
                value={config.mass_mention_threshold}
                min={2}
                max={30}
                onChange={(value) =>
                  setConfig((current) => ({
                    ...current,
                    mass_mention_threshold: value,
                  }))
                }
              />
              <ActionSelect
                label={d.actionMassMentions}
                value={config.mass_mention_action}
                options={actionOptions}
                onChange={(value) =>
                  setConfig((current) => ({
                    ...current,
                    mass_mention_action: value,
                  }))
                }
              />
            </>
          ) : null}

          <NumberField
            label={d.timeoutMinutes}
            value={config.timeout_minutes}
            min={1}
            max={40320}
            onChange={(value) =>
              setConfig((current) => ({ ...current, timeout_minutes: value }))
            }
          />
        </div>
      </FeatureConfigurationModal>

      <FeatureConfigurationModal
        visible={activeModal === "exemptions"}
        title={d.exemptionsTitle}
        description={d.exemptionsModalDesc}
        category="moderation"
        icon={cilShieldAlt}
        saving={saving}
        error={saveError}
        onClose={() => setActiveModal(null)}
        onSave={handleModalSave}
      >
        <div className="d-flex flex-column gap-3">
          <ToggleLine
            label={d.exemptManageMessages}
            checked={config.exempt_manage_messages}
            onChange={(checked) =>
              setConfig((current) => ({
                ...current,
                exempt_manage_messages: checked,
              }))
            }
          />
          <p className="mb-0 small text-body-secondary">
            {d.exemptManageHelp}
          </p>

          <div>
            <CFormLabel className="mb-2">{d.exemptChannels}</CFormLabel>
            <div className="d-flex flex-wrap gap-2">
              {channels.map((channel) => {
                const isSelected = config.exempt_channel_ids.includes(channel.id);
                return (
                  <Button
                    key={channel.id}
                    type="button"
                    size="sm"
                    variant={isSelected ? "primary" : "secondary"}
                    onClick={() => toggleId("exempt_channel_ids", channel.id)}
                  >
                    #{channel.name}
                  </Button>
                );
              })}
            </div>
          </div>

          <div>
            <CFormLabel className="mb-2">{d.exemptRoles}</CFormLabel>
            <div className="d-flex flex-wrap gap-2">
              {roles.map((role) => {
                const isSelected = config.exempt_role_ids.includes(role.id);
                return (
                  <Button
                    key={role.id}
                    type="button"
                    size="sm"
                    variant={isSelected ? "primary" : "secondary"}
                    onClick={() => toggleId("exempt_role_ids", role.id)}
                  >
                    @{role.name}
                  </Button>
                );
              })}
            </div>
          </div>
        </div>
      </FeatureConfigurationModal>
    </div>
  );
}

function ToggleLine({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="d-flex align-items-center justify-content-between gap-3 border rounded p-3">
      <div>
        <div className="fw-medium">{label}</div>
        {description ? (
          <p className="mb-0 mt-1 small text-body-secondary">{description}</p>
        ) : null}
      </div>
      <Switch checked={checked} onChange={onChange} aria-label={label} />
    </div>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  onChange,
  defaultValue,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
  defaultValue?: number;
}) {
  return (
    <div>
      <CFormLabel>{label}</CFormLabel>
      <NumberInput
        value={value}
        defaultValue={defaultValue ?? min}
        min={min}
        max={max}
        step={1}
        aria-label={label}
        onCommit={onChange}
      />
    </div>
  );
}

function ActionSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: AutomodAction;
  options: { value: AutomodAction; label: string }[];
  onChange: (value: AutomodAction) => void;
}) {
  return (
    <div>
      <CFormLabel>{label}</CFormLabel>
      <CFormSelect
        value={value}
        onChange={(event) => onChange(event.target.value as AutomodAction)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </CFormSelect>
    </div>
  );
}

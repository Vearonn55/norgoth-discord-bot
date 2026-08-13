"use client";

import { useEffect } from "react";
import { CAlert, CCol, CRow, CSpinner } from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useFirstGuild } from "@/lib/use-first-guild";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";
import { useModulesStore } from "@/stores/modules-store";

export function ModuleTogglesPanel() {
  const dict = useLocaleDict();
  const d = dict.moduleTogglesPage;
  const { guildId, loading: guildLoading, error: guildError, reload } =
    useFirstGuild();

  const modules = useModulesStore((s) => s.modules);
  const loading = useModulesStore((s) => s.loading);
  const error = useModulesStore((s) => s.error);
  const pendingKey = useModulesStore((s) => s.pendingKey);
  const load = useModulesStore((s) => s.load);
  const toggleModule = useModulesStore((s) => s.toggleModule);

  useEffect(() => {
    if (!guildId) return;
    void load(guildId);
  }, [guildId, load]);

  if (guildLoading || loading) {
    return (
      <Card>
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          {d.loading}
        </div>
      </Card>
    );
  }

  if ((guildError || !guildId) && modules.length === 0) {
    return (
      <Card>
        <div className="d-flex flex-column gap-3">
          <Badge variant="warning">{d.unavailable}</Badge>
          <p className="mb-0 small text-body-secondary">
            {guildError ?? d.botOffline}
          </p>
          <div>
            <Button variant="secondary" onClick={() => void reload()}>
              {d.retry}
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  if (error && modules.length === 0) {
    return (
      <Card>
        <div className="d-flex flex-column gap-3">
          <Badge variant="warning">{d.unavailable}</Badge>
          <p className="mb-0 small text-body-secondary">{error}</p>
          <div>
            <Button
              variant="secondary"
              onClick={() => guildId && void load(guildId)}
            >
              {d.retry}
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  const enabledCount = modules.filter((module) => module.enabled).length;

  return (
    <Card>
      <div className="d-flex flex-column gap-4">
        <div className="d-flex align-items-center justify-content-between gap-3">
          <div>
            <h2 className="h5 mb-0 fw-semibold">{d.title}</h2>
            <p className="mt-1 mb-0 small text-body-secondary">
              {d.description}
            </p>
          </div>

          <Badge variant="info">
            {formatDict(d.enabledCount, {
              enabled: enabledCount,
              total: modules.length,
            })}
          </Badge>
        </div>

        {error ? (
          <CAlert color="danger" className="mb-0">
            {error}
          </CAlert>
        ) : null}

        <CRow className="g-3">
          {modules.map((module) => (
            <CCol key={module.key} xl={6}>
              <div className="d-flex align-items-center justify-content-between gap-3 border rounded px-3 py-2 h-100">
                <div className="min-w-0">
                  <div className="small fw-medium">{module.name}</div>
                  <p className="mt-1 mb-0 small text-body-secondary">
                    {module.description}
                  </p>
                </div>

                <Switch
                  checked={module.enabled}
                  disabled={pendingKey === module.key || !guildId}
                  onChange={(checked) =>
                    guildId && void toggleModule(guildId, module.key, checked)
                  }
                  aria-label={module.name}
                />
              </div>
            </CCol>
          ))}
        </CRow>
      </div>
    </Card>
  );
}

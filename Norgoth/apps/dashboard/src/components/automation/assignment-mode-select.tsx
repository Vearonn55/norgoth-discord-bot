"use client";

import { CFormLabel, CFormSelect } from "@coreui/react";
import {
  ROLE_MENU_MODES,
  type RoleMenuMode,
} from "@/lib/discord/role-menu-modes";
import { useLocaleDict } from "@/lib/locale-dict";

type AssignmentModeSelectProps = {
  value: RoleMenuMode;
  onChange: (mode: RoleMenuMode) => void;
};

export function AssignmentModeSelect({
  value,
  onChange,
}: AssignmentModeSelectProps) {
  const dict = useLocaleDict();
  const d = dict.roleMenusPage;

  const labels: Record<RoleMenuMode, string> = {
    toggle: d.modeToggle,
    give: d.modeGive,
    take: d.modeTake,
  };
  const help: Record<RoleMenuMode, string> = {
    toggle: d.modeToggleHelp,
    give: d.modeGiveHelp,
    take: d.modeTakeHelp,
  };

  return (
    <div>
      <CFormLabel className="small">{d.whenClicked}</CFormLabel>
      <CFormSelect
        value={value}
        onChange={(e) => onChange(e.target.value as RoleMenuMode)}
      >
        {ROLE_MENU_MODES.map((mode) => (
          <option key={mode} value={mode}>
            {labels[mode]}
          </option>
        ))}
      </CFormSelect>
      <p className="mb-0 mt-1 small text-body-secondary">{help[value]}</p>
    </div>
  );
}

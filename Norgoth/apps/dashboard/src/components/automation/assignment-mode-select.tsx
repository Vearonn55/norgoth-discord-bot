"use client";

import { CFormLabel, CFormSelect } from "@coreui/react";
import {
  ROLE_MENU_MODES,
  ROLE_MENU_MODE_HELP,
  ROLE_MENU_MODE_LABELS,
  type RoleMenuMode,
} from "@/lib/discord/role-menu-modes";

type AssignmentModeSelectProps = {
  value: RoleMenuMode;
  onChange: (mode: RoleMenuMode) => void;
};

export function AssignmentModeSelect({
  value,
  onChange,
}: AssignmentModeSelectProps) {
  return (
    <div>
      <CFormLabel className="small">When clicked / selected</CFormLabel>
      <CFormSelect
        value={value}
        onChange={(e) => onChange(e.target.value as RoleMenuMode)}
      >
        {ROLE_MENU_MODES.map((mode) => (
          <option key={mode} value={mode}>
            {ROLE_MENU_MODE_LABELS[mode]}
          </option>
        ))}
      </CFormSelect>
      <p className="mb-0 mt-1 small text-body-secondary">
        {ROLE_MENU_MODE_HELP[value]}
      </p>
    </div>
  );
}

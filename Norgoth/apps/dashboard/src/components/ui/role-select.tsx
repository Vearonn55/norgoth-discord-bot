"use client";

import { CFormSelect } from "@coreui/react";
import type { GuildRole } from "@/stores/guild-store";

type RoleSelectProps = {
  roles: GuildRole[];
  value: string;
  onChange: (value: string) => void;
  allowEmpty?: boolean;
  emptyLabel?: string;
  multiple?: boolean;
  values?: string[];
  onChangeMultiple?: (values: string[]) => void;
};

export function RoleSelect({
  roles,
  value,
  onChange,
  allowEmpty = true,
  emptyLabel = "Select role…",
  multiple = false,
  values = [],
  onChangeMultiple,
}: RoleSelectProps) {
  if (multiple) {
    return (
      <CFormSelect
        multiple
        value={values}
        htmlSize={Math.min(8, Math.max(3, roles.length))}
        onChange={(e) => {
          const selected = Array.from(e.target.selectedOptions).map((o) => o.value);
          onChangeMultiple?.(selected);
        }}
      >
        {roles.map((role) => (
          <option key={role.id} value={role.id} style={{ color: role.color || undefined }}>
            {role.name}
          </option>
        ))}
      </CFormSelect>
    );
  }

  return (
    <CFormSelect value={value} onChange={(e) => onChange(e.target.value)}>
      {allowEmpty ? <option value="">{emptyLabel}</option> : null}
      {roles.map((role) => (
        <option key={role.id} value={role.id}>
          {role.name}
        </option>
      ))}
    </CFormSelect>
  );
}

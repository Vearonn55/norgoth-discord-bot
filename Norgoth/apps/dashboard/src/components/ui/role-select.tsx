"use client";

import { CFormSelect } from "@coreui/react";
import type { GuildRole } from "@/stores/guild-store";
import { useLocaleDict } from "@/lib/locale-dict";

type RoleSelectProps = {
  roles: GuildRole[];
  value: string;
  onChange: (value: string) => void;
  allowEmpty?: boolean;
  emptyLabel?: string;
  multiple?: boolean;
  values?: string[];
  onChangeMultiple?: (values: string[]) => void;
  id?: string;
  className?: string;
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
  id,
  className,
}: RoleSelectProps) {
  const dict = useLocaleDict();
  const selectedMissing =
    Boolean(value) && !roles.some((role) => role.id === value);
  const missingValues = values.filter(
    (id) => !roles.some((role) => role.id === id),
  );

  if (multiple) {
    return (
      <CFormSelect
        id={id}
        className={className}
        multiple
        value={values}
        htmlSize={Math.min(8, Math.max(3, roles.length + missingValues.length))}
        onChange={(e) => {
          const selected = Array.from(e.target.selectedOptions).map((o) => o.value);
          onChangeMultiple?.(selected);
        }}
      >
        {missingValues.map((id) => (
          <option key={id} value={id} disabled>
            {dict.common.roleUnavailable}
          </option>
        ))}
        {roles.map((role) => (
          <option key={role.id} value={role.id} style={{ color: role.color || undefined }}>
            {role.name}
          </option>
        ))}
      </CFormSelect>
    );
  }

  return (
    <CFormSelect
      id={id}
      className={className}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {allowEmpty ? <option value="">{emptyLabel}</option> : null}
      {selectedMissing ? (
        <option value={value} disabled>
          {dict.common.roleUnavailable}
        </option>
      ) : null}
      {roles.map((role) => (
        <option key={role.id} value={role.id}>
          {role.name}
        </option>
      ))}
    </CFormSelect>
  );
}

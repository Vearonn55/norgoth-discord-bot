"use client";

import {
  ROLE_MENU_INTERACTION_HELP,
  ROLE_MENU_INTERACTION_LABELS,
  ROLE_MENU_INTERACTIONS,
  type RoleMenuInteraction,
} from "@/lib/discord/role-menu-modes";

type AssignmentMethodSelectorProps = {
  value: RoleMenuInteraction;
  onChange: (value: RoleMenuInteraction) => void;
};

export function AssignmentMethodSelector({
  value,
  onChange,
}: AssignmentMethodSelectorProps) {
  return (
    <div className="d-flex flex-column gap-2">
      <div className="fw-semibold">How members choose roles</div>
      <div
        className="row g-2"
        role="radiogroup"
        aria-label="Role assignment method"
      >
        {ROLE_MENU_INTERACTIONS.map((method) => {
          const selected = value === method;
          return (
            <div key={method} className="col-md-4">
              <button
                type="button"
                role="radio"
                aria-checked={selected}
                className={[
                  "btn w-100 h-100 text-start",
                  selected ? "btn-primary" : "btn-outline-secondary",
                ].join(" ")}
                onClick={() => onChange(method)}
              >
                <div className="fw-semibold">
                  {ROLE_MENU_INTERACTION_LABELS[method]}
                </div>
                <div className="small opacity-75 mt-1">
                  {ROLE_MENU_INTERACTION_HELP[method]}
                </div>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

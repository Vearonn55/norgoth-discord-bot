"use client";

import {
  ROLE_MENU_INTERACTIONS,
  type RoleMenuInteraction,
} from "@/lib/discord/role-menu-modes";
import { useLocaleDict } from "@/lib/locale-dict";

type AssignmentMethodSelectorProps = {
  value: RoleMenuInteraction;
  onChange: (value: RoleMenuInteraction) => void;
};

export function AssignmentMethodSelector({
  value,
  onChange,
}: AssignmentMethodSelectorProps) {
  const dict = useLocaleDict();
  const d = dict.roleMenusPage;

  const labels: Record<RoleMenuInteraction, string> = {
    buttons: d.interactionButtons,
    select: d.interactionSelect,
    reactions: d.interactionReactions,
  };
  const help: Record<RoleMenuInteraction, string> = {
    buttons: d.interactionButtonsHelp,
    select: d.interactionSelectHelp,
    reactions: d.interactionReactionsHelp,
  };

  return (
    <div className="d-flex flex-column gap-2">
      <div className="fw-semibold">{d.howMembersChoose}</div>
      <div
        className="row g-2"
        role="radiogroup"
        aria-label={d.assignmentMethodAria}
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
                <div className="fw-semibold">{labels[method]}</div>
                <div className="small opacity-75 mt-1">{help[method]}</div>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

"use client";

import { Fragment } from "react";

export type StepperStep = {
  id: string;
  label: string;
};

type StepperProps = {
  steps: StepperStep[];
  /** Zero-based index of the current step. */
  current: number;
  /** Optional: allow clicking a previously completed step. */
  onStepClick?: (index: number) => void;
};

/**
 * Dependency-free horizontal stepper. CoreUI has no stepper primitive, so this
 * mirrors the existing bespoke campaign-wizard progress pattern.
 */
export function Stepper({ steps, current, onStepClick }: StepperProps) {
  return (
    <div className="norgoth-stepper" role="list">
      {steps.map((step, index) => {
        const isActive = index === current;
        const isComplete = index < current;
        const clickable = onStepClick && index <= current;
        return (
          <Fragment key={step.id}>
            {index > 0 ? (
              <span
                className={[
                  "norgoth-stepper-connector",
                  index <= current ? "is-complete" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                aria-hidden
              />
            ) : null}
            <div
              role="listitem"
              className={[
                "norgoth-stepper-step",
                isActive ? "is-active" : "",
                isComplete ? "is-complete" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <button
                type="button"
                className="norgoth-stepper-index"
                disabled={!clickable}
                onClick={clickable ? () => onStepClick?.(index) : undefined}
                aria-current={isActive ? "step" : undefined}
                style={clickable ? { cursor: "pointer" } : { cursor: "default" }}
              >
                {isComplete ? "✓" : index + 1}
              </button>
              <span className="small fw-medium d-none d-md-inline">
                {step.label}
              </span>
            </div>
          </Fragment>
        );
      })}
    </div>
  );
}

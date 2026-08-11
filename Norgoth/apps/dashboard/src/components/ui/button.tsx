"use client";

import {
  isValidElement,
  type ButtonHTMLAttributes,
  type ElementType,
  type ReactElement,
  type ReactNode,
} from "react";
import { CButton } from "@coreui/react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  asChild?: boolean;
  children?: ReactNode;
};

function mapVariant(variant: ButtonVariant): {
  color: string;
  buttonVariant?: "outline" | "ghost";
} {
  switch (variant) {
    case "primary":
      return { color: "primary" };
    case "danger":
      return { color: "danger" };
    case "ghost":
      return { color: "light", buttonVariant: "ghost" };
    case "secondary":
    default:
      return { color: "light", buttonVariant: "outline" };
  }
}

function mapSize(size: ButtonSize): "sm" | "lg" | undefined {
  if (size === "sm") return "sm";
  if (size === "lg") return "lg";
  return undefined;
}

export function Button({
  className,
  variant = "secondary",
  size = "md",
  asChild = false,
  children,
  type = "button",
  ...props
}: ButtonProps) {
  const mapped = mapVariant(variant);
  const coreSize = mapSize(size);

  if (asChild && isValidElement(children)) {
    const child = children as ReactElement<{
      className?: string;
      children?: ReactNode;
    }>;

    return (
      <CButton
        as={child.type as ElementType}
        color={mapped.color}
        variant={mapped.buttonVariant}
        size={coreSize}
        {...(child.props as object)}
        {...props}
        className={[className, child.props.className].filter(Boolean).join(" ")}
      >
        {child.props.children}
      </CButton>
    );
  }

  return (
    <CButton
      type={type}
      color={mapped.color}
      variant={mapped.buttonVariant}
      size={coreSize}
      className={className}
      {...props}
    >
      {children}
    </CButton>
  );
}

"use client";

import { CIcon } from "@coreui/icons-react";
import type { ComponentProps } from "react";

type IconProps = ComponentProps<typeof CIcon>;

export function Icon(props: IconProps) {
  return <CIcon {...props} />;
}

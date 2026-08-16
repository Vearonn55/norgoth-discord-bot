"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  parseCnUrlState,
  serializeCnUrlState,
  type CnUrlState,
} from "@/lib/cn-url-state";

export function useCnUrlState() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const state = useMemo(
    () => parseCnUrlState(searchParams),
    [searchParams]
  );

  const replaceState = useCallback(
    (next: CnUrlState) => {
      const qs = serializeCnUrlState(next);
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [pathname, router]
  );

  const patchState = useCallback(
    (patch: Partial<CnUrlState>) => {
      replaceState({ ...state, ...patch });
    },
    [replaceState, state]
  );

  return { state, replaceState, patchState };
}

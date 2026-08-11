"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import {
  defaultCampaignWizardState,
  type CampaignWizardState,
} from "@/types/campaign";

export const CAMPAIGN_WIZARD_DRAFT_KEY = "norgoth:campaign-wizard-draft:v1";
export const CAMPAIGN_WIZARD_DRAFT_VERSION = 1;

export type CampaignWizardDraft = {
  version: number;
  step: number;
  wizardState: CampaignWizardState;
  updatedAt: string;
};

type DraftState = {
  draft: CampaignWizardDraft | null;
  bannerDismissed: boolean;
  hasDraft: () => boolean;
  saveDraft: (step: number, wizardState: CampaignWizardState) => void;
  discardDraft: () => void;
  startNew: () => void;
  setBannerDismissed: (value: boolean) => void;
};

export const useCampaignWizardDraftStore = create<DraftState>()(
  persist(
    (set, get) => ({
      draft: null,
      bannerDismissed: false,
      hasDraft: () => {
        const draft = get().draft;
        if (!draft) return false;
        const name = draft.wizardState.basics.name.trim();
        const body = draft.wizardState.message.body.trim();
        return Boolean(name || body || draft.step > 1);
      },
      saveDraft: (step, wizardState) =>
        set({
          draft: {
            version: CAMPAIGN_WIZARD_DRAFT_VERSION,
            step,
            wizardState,
            updatedAt: new Date().toISOString(),
          },
          bannerDismissed: true,
        }),
      discardDraft: () => set({ draft: null, bannerDismissed: true }),
      startNew: () =>
        set({
          draft: {
            version: CAMPAIGN_WIZARD_DRAFT_VERSION,
            step: 1,
            wizardState: defaultCampaignWizardState,
            updatedAt: new Date().toISOString(),
          },
          bannerDismissed: true,
        }),
      setBannerDismissed: (bannerDismissed) => set({ bannerDismissed }),
    }),
    {
      name: CAMPAIGN_WIZARD_DRAFT_KEY,
      version: CAMPAIGN_WIZARD_DRAFT_VERSION,
      migrate: (persisted) => {
        // Stub for future draft schema migrations.
        return persisted as DraftState;
      },
      partialize: (state) => ({
        draft: state.draft,
      }),
    }
  )
);

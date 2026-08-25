import { create } from 'zustand';
import { useWorksheetStore } from '../store/useWorksheetStore';

export interface UnsavedPromptOptions {
  actionTitle?: string;
  actionDescription: string;
  onProceed: () => any | Promise<any>;
}

interface UnsavedGuardState {
  isOpen: boolean;
  actionTitle: string;
  actionDescription: string;
  onProceed: (() => any | Promise<any>) | null;
  openPrompt: (options: UnsavedPromptOptions) => void;
  closePrompt: () => void;
}

export const useUnsavedPromptStore = create<UnsavedGuardState>((set) => ({
  isOpen: false,
  actionTitle: 'Unsaved Changes',
  actionDescription: 'performing this action',
  onProceed: null,

  openPrompt: ({ actionTitle = 'Unsaved Changes', actionDescription, onProceed }) => {
    set({
      isOpen: true,
      actionTitle,
      actionDescription,
      onProceed,
    });
  },

  closePrompt: () => {
    set({
      isOpen: false,
      onProceed: null,
    });
  },
}));

/**
 * Guards an action: if the project has unsaved changes (isDirty === true),
 * opens the Unsaved Changes confirmation dialog. Otherwise, immediately executes onProceed.
 */
export const guardUnsavedChanges = (
  onProceed: () => any | Promise<any>,
  actionDescription: string = 'proceeding',
  actionTitle: string = 'Unsaved Changes'
) => {
  const isDirty = useWorksheetStore.getState().isDirty;
  if (isDirty) {
    useUnsavedPromptStore.getState().openPrompt({
      actionTitle,
      actionDescription,
      onProceed,
    });
  } else {
    onProceed();
  }
};

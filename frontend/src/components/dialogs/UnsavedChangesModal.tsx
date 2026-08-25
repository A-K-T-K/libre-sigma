import React, { useState } from 'react';
import { Button, Spinner } from '@fluentui/react-components';
import {
  WarningRegular,
  SaveRegular,
  DismissRegular,
  DeleteRegular,
} from '@fluentui/react-icons';
import { useUnsavedPromptStore } from '../../hooks/useUnsavedGuard';
import { useWorksheetStore } from '../../store/useWorksheetStore';
import { useSessionStore } from '../../store/useSessionStore';
import { saveProjectLtb } from '../../utils/projectIo';

export const UnsavedChangesModal: React.FC = () => {
  const { isOpen, actionTitle, actionDescription, onProceed, closePrompt } = useUnsavedPromptStore();
  const activeSheet = useWorksheetStore((s) => s.getActiveWorksheet());
  const worksheets = useWorksheetStore((s) => s.worksheets);
  const sessionItems = useSessionStore((s) => s.items);
  const [isSaving, setIsSaving] = useState(false);

  if (!isOpen) return null;

  const projectName = activeSheet?.name || 'Untitled Project';

  const handleSaveAndProceed = async () => {
    setIsSaving(true);
    try {
      const saved = await saveProjectLtb(false);
      if (saved) {
        const proceedFn = onProceed;
        closePrompt();
        if (proceedFn) {
          await proceedFn();
        }
      }
    } catch (err) {
      console.error('[UnsavedChangesModal] Save failed:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDontSaveAndProceed = async () => {
    const proceedFn = onProceed;
    useWorksheetStore.getState().setIsDirty(false);
    closePrompt();
    if (proceedFn) {
      await proceedFn();
    }
  };

  const handleCancel = () => {
    closePrompt();
  };

  return (
    <div
      className="fixed inset-0 z-[120] flex items-center justify-center bg-black/45 backdrop-blur-[1.5px] p-4 select-none animate-in fade-in duration-150"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSaving) handleCancel();
      }}
    >
      <div className="bg-white rounded-xl shadow-2xl border border-[#d2d0ce] w-full max-w-[460px] overflow-hidden flex flex-col animate-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-[#fff8f2] border-b border-[#fed9cc]">
          <div className="flex items-center space-x-2.5">
            <div className="w-7 h-7 rounded-full bg-[#fde7d9] text-[#d83b01] flex items-center justify-center shadow-xs">
              <WarningRegular className="w-4 h-4" />
            </div>
            <h2 className="text-sm font-bold text-[#201f1e]">
              {actionTitle || 'Unsaved Changes'}
            </h2>
          </div>
          <Button
            appearance="subtle"
            size="small"
            icon={<DismissRegular />}
            onClick={handleCancel}
            disabled={isSaving}
            style={{ minWidth: '28px', padding: 0 }}
          />
        </div>

        {/* Content */}
        <div className="p-5 space-y-3.5 text-xs text-[#323130] leading-relaxed">
          <p className="text-[13px] font-medium text-[#201f1e]">
            Do you want to save changes to <span className="font-bold text-[#008450]">"{projectName}"</span> before {actionDescription}?
          </p>

          <div className="bg-[#f8f9fa] border border-[#e1dfdd] rounded-lg p-3 space-y-1.5 text-[11.5px] text-[#605e5c]">
            <div className="flex justify-between">
              <span>Worksheets:</span>
              <span className="font-semibold text-[#201f1e]">{worksheets.length} sheet{worksheets.length > 1 ? 's' : ''}</span>
            </div>
            {sessionItems.length > 0 && (
              <div className="flex justify-between">
                <span>Session outputs:</span>
                <span className="font-semibold text-[#201f1e]">{sessionItems.length} result{sessionItems.length > 1 ? 's' : ''}</span>
              </div>
            )}
            <p className="text-[11px] text-[#a80000] pt-1 border-t border-[#edebe9]">
              If you don't save, all unsaved edits and statistical outputs will be lost.
            </p>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="px-5 py-3.5 bg-[#f3f2f1] border-t border-[#e1dfdd] flex items-center justify-between">
          <Button
            appearance="subtle"
            size="medium"
            onClick={handleCancel}
            disabled={isSaving}
          >
            Cancel
          </Button>

          <div className="flex items-center space-x-2">
            <Button
              appearance="secondary"
              size="medium"
              icon={<DeleteRegular className="text-[#a80000]" />}
              onClick={handleDontSaveAndProceed}
              disabled={isSaving}
              className="text-[#a80000] hover:bg-[#fde7e9] hover:border-[#a80000]"
            >
              Don't Save
            </Button>

            <Button
              appearance="primary"
              size="medium"
              icon={isSaving ? <Spinner size="extra-tiny" /> : <SaveRegular />}
              onClick={handleSaveAndProceed}
              disabled={isSaving}
              style={{ backgroundColor: '#008450', borderColor: '#008450' }}
            >
              {isSaving ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

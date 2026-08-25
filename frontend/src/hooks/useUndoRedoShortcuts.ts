import { useEffect } from 'react';
import { useWorksheetStore } from '../store/useWorksheetStore';
import { openProjectFileDialog, saveProjectLtb, exportProjectXlsx, printSessionReport } from '../utils/projectIo';
import { guardUnsavedChanges } from './useUnsavedGuard';

/**
 * Global keyboard shortcut hook for Undo / Redo / File Operations.
 *
 *   Ctrl+Z       → Undo
 *   Ctrl+Y       → Redo
 *   Ctrl+Shift+Z → Redo
 *   Ctrl+N       → New Project
 *   Ctrl+S       → Save Project (.ltb)
 *   Ctrl+Shift+S → Save Project As (.ltb)
 *   Ctrl+O       → Open Project / Data (.ltb, .xlsx, .csv)
 *   Ctrl+P       → Print / Export PDF Report
 *   Ctrl+I       → Import Excel (.xlsx)
 *   Ctrl+E       → Export Excel (.xlsx)
 */
export function useUndoRedoShortcuts() {
  const undo = useWorksheetStore((s) => s.undo);
  const redo = useWorksheetStore((s) => s.redo);
  const clearRange = useWorksheetStore((s) => s.clearRange);
  const cutCells = useWorksheetStore((s) => s.cutCells);
  const copyCells = useWorksheetStore((s) => s.copyCells);
  const pasteCells = useWorksheetStore((s) => s.pasteCells);
  const activeSheetId = useWorksheetStore((s) => s.activeSheetId);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't intercept when user is typing in a native input/textarea
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if ((e.target as HTMLElement)?.isContentEditable) return;

      const isCtrl = e.ctrlKey || e.metaKey;

      if (isCtrl) {
        if (e.key === 'z' || e.key === 'Z') {
          if (e.shiftKey) {
            e.preventDefault();
            redo();
          } else {
            e.preventDefault();
            undo();
          }
        } else if (e.key === 'y' || e.key === 'Y') {
          e.preventDefault();
          redo();
        } else if (e.key === 'n' || e.key === 'N') {
          e.preventDefault();
          guardUnsavedChanges(
            () => useWorksheetStore.getState().createNewProject(),
            'creating a new project',
            'New Project'
          );
        } else if (e.key === 's' || e.key === 'S') {
          e.preventDefault();
          if (e.shiftKey) {
            saveProjectLtb(true);
          } else {
            saveProjectLtb(false);
          }
        } else if (e.key === 'o' || e.key === 'O') {
          e.preventDefault();
          guardUnsavedChanges(
            () => openProjectFileDialog(),
            'opening another file',
            'Open Project'
          );
        } else if (e.key === 'p' || e.key === 'P') {
          e.preventDefault();
          printSessionReport();
        } else if (e.key === 'i' || e.key === 'I') {
          e.preventDefault();
          guardUnsavedChanges(
            () => openProjectFileDialog(),
            'importing an Excel file',
            'Import Excel'
          );
        } else if (e.key === 'e' || e.key === 'E') {
          e.preventDefault();
          exportProjectXlsx();
        } else if (e.key === 'x' || e.key === 'X') {
          if (activeSheetId) {
            e.preventDefault();
            cutCells(activeSheetId);
          }
        }
      } else if (e.key === 'Delete') {
        if (activeSheetId) {
          e.preventDefault();
          clearRange(activeSheetId);
        }
      }
    };



    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [undo, redo, clearRange, cutCells, copyCells, pasteCells, activeSheetId]);
}

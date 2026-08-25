import React, { useEffect, useRef, useState } from 'react';
import { ChevronRightRegular } from '@fluentui/react-icons';
import { MenuNode } from '../../types';
import { usePluginStore } from '../../store/usePluginStore';
import { useWorksheetStore } from '../../store/useWorksheetStore';
import { useSessionStore } from '../../store/useSessionStore';
import { getMenuOrPluginIcon } from '../../utils/menuIcons';
import { openProjectFileDialog, saveProjectLtb, exportProjectXlsx, printSessionReport } from '../../utils/projectIo';
import { guardUnsavedChanges } from '../../hooks/useUnsavedGuard';

interface TopMenuProps {
  onOpenSampleModal: () => void;
  onOpenImportCsvModal: () => void;
  onOpenAboutModal: () => void;
  onOpenPatternedModal: () => void;
  onOpenSortModal: () => void;
  onOpenStackModal: () => void;
  onOpenUnstackModal: () => void;
  onOpenRecodeModal: () => void;
  onOpenSubsetModal: () => void;
}

export const TopMenu: React.FC<TopMenuProps> = ({
  onOpenSampleModal,
  onOpenImportCsvModal,
  onOpenAboutModal,
  onOpenPatternedModal,
  onOpenSortModal,
  onOpenStackModal,
  onOpenUnstackModal,
  onOpenRecodeModal,
  onOpenSubsetModal,
}) => {
  const { getMenuTree, openDialog } = usePluginStore();
  const {
    createSheet,
    createNewProject,
    clearSheet,
    clearRange,
    deleteCells,
    copyCells,
    cutCells,
    pasteCells,
    undo,
    redo,
    _undoStack,
    _redoStack,
    activeSheetId,
    getActiveWorksheet,
    addRow,
    addColumn,
  } = useWorksheetStore();
  const { clearSession, exportSessionText } = useSessionStore();

  const [activeRootId, setActiveRootId] = useState<string | null>(null);
  const menuBarRef = useRef<HTMLDivElement>(null);
  const menuTree = getMenuTree();

  // Close menus when clicking outside or pressing Escape
  useEffect(() => {
    const handleDocumentClick = (e: MouseEvent) => {
      if (menuBarRef.current && !menuBarRef.current.contains(e.target as Node)) {
        setActiveRootId(null);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setActiveRootId(null);
      }
    };

    document.addEventListener('mousedown', handleDocumentClick);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleDocumentClick);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const handleAction = (item: MenuNode) => {
    setActiveRootId(null);


    if (item.pluginId) {
      openDialog(item.pluginId);
      return;
    }

    switch (item.id) {
      case 'file-new':
        guardUnsavedChanges(() => createNewProject(), 'creating a new project', 'New Project');
        break;
      case 'file-new-sheet':
        createSheet();
        break;
      case 'file-open-project':
        guardUnsavedChanges(() => openProjectFileDialog(), 'opening another file', 'Open Project');
        break;
      case 'file-save-project':
        saveProjectLtb(false);
        break;
      case 'file-save-as-project':
        saveProjectLtb(true);
        break;
      case 'file-import-xlsx':
        guardUnsavedChanges(() => openProjectFileDialog(), 'importing an Excel file', 'Import Excel');
        break;
      case 'file-export-xlsx':
        exportProjectXlsx();
        break;
      case 'file-print-report':
        printSessionReport();
        break;
      case 'file-sample':
        guardUnsavedChanges(() => onOpenSampleModal(), 'loading a sample dataset', 'Open Sample Dataset');
        break;
      case 'file-import-csv':
        guardUnsavedChanges(() => onOpenImportCsvModal(), 'importing CSV data', 'Import CSV');
        break;


      case 'file-export-csv': {
        const sheet = getActiveWorksheet();
        if (sheet) {
          const headers = sheet.columns.map((c) => c.name || c.id).join(',');
          const rowLines = sheet.rows.map((r) => sheet.columns.map((c) => r[c.id] ?? '').join(','));
          const csvContent = [headers, ...rowLines].join('\n');
          const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = `${sheet.name.replace(/\s+/g, '_')}.csv`;
          link.click();
          URL.revokeObjectURL(url);
        }
        break;
      }
      case 'file-export-session': {
        const text = exportSessionText();
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `openminitab_session.txt`;
        link.click();
        URL.revokeObjectURL(url);
        break;
      }
      case 'edit-undo':
        undo();
        break;
      case 'edit-redo':
        redo();
        break;
      case 'edit-clear-cells':
        if (activeSheetId) clearRange(activeSheetId);
        break;
      case 'edit-delete-cells':
        if (activeSheetId) deleteCells(activeSheetId);
        break;
      case 'edit-copy-cells':
        if (activeSheetId) copyCells(activeSheetId);
        break;
      case 'edit-cut-cells':
        if (activeSheetId) cutCells(activeSheetId);
        break;
      case 'edit-paste-cells':
        if (activeSheetId) pasteCells(activeSheetId);
        break;
      case 'edit-clear-sheet':
        if (activeSheetId) clearSheet(activeSheetId);
        break;
      case 'edit-clear-session':
        clearSession();
        break;
      case 'edit-insert-col':
        if (activeSheetId) addColumn(activeSheetId);
        break;
      case 'edit-insert-row':
        if (activeSheetId) addRow(activeSheetId);
        break;
      case 'data-patterned':
        onOpenPatternedModal();
        break;
      case 'data-sort':
        onOpenSortModal();
        break;
      case 'data-stack':
        onOpenStackModal();
        break;
      case 'data-unstack':
        onOpenUnstackModal();
        break;
      case 'data-recode':
        onOpenRecodeModal();
        break;
      case 'data-subset':
        onOpenSubsetModal();
        break;
      case 'calc-random': {
        const sheet = getActiveWorksheet();
        if (sheet) {
          const colId = `c${sheet.columns.length + 1}`;
          addColumn(sheet.id);
          for (let i = 0; i < 25; i++) {
            const u = Math.random();
            const v = Math.random();
            const norm = Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
            const val = parseFloat((100 + norm * 15).toFixed(2));
            useWorksheetStore.getState().setCell(sheet.id, i, colId, val);
          }
          useWorksheetStore.getState().setColumnName(sheet.id, colId, 'Norm_Rand');
        }
        break;
      }
      case 'help-about':
        onOpenAboutModal();
        break;
      default:
        break;
    }
  };



  const activeSheet = getActiveWorksheet();
  const designType = activeSheet?.designMeta?.type;
  const sheetName = (activeSheet?.name || '').toLowerCase();
  const cols = activeSheet?.columns || [];
  const hasStdRun = cols.some((c) => /^(stdorder|runorder)$/i.test(c.name || ''));

  const hasTaguchiDesign = Boolean(
    activeSheet && activeSheet.rows.length >= 4 && (
      designType === 'taguchi' ||
      (hasStdRun && sheetName.includes('taguchi'))
    )
  );

  const hasFactorialDesign = Boolean(
    activeSheet && activeSheet.rows.length >= 4 && (
      designType === 'factorial' ||
      (hasStdRun && (sheetName.includes('factorial') || !sheetName.includes('taguchi') && !sheetName.includes('rsm') && !sheetName.includes('mixture')))
    )
  );

  const hasRsmDesign = Boolean(
    activeSheet && activeSheet.rows.length >= 4 && (
      designType === 'rsm' ||
      (hasStdRun && sheetName.includes('rsm'))
    )
  );

  const hasMixtureDesign = Boolean(
    activeSheet && activeSheet.rows.length >= 4 && (
      designType === 'mixture' ||
      (hasStdRun && sheetName.includes('mixture'))
    )
  );

  // Recursive cascading submenu renderer
  const renderMenuItems = (items: MenuNode[], depth = 0) => {
    return (
      <div
        className={`bg-white border border-[#d2d0ce] shadow-xl py-1 rounded-md min-w-[240px] text-xs text-[#201f1e] ${
          depth === 0 ? 'absolute top-full left-0 z-50' : 'absolute top-0 left-full z-50 -ml-px -mt-1'
        }`}
      >
        {items.map((item) => {
          if (item.divider) {
            return <div key={item.id} className="h-px bg-[#edebe9] my-1" />;
          }

          const hasChildren = Boolean(item.children && item.children.length > 0);

          let isDisabled = false;
          let disabledReason = '';

          if (item.id === 'edit-undo' && _undoStack.length === 0) {
            isDisabled = true;
          } else if (item.id === 'edit-redo' && _redoStack.length === 0) {
            isDisabled = true;
          } else if (item.pluginId === 'doe_analyze_taguchi' && !hasTaguchiDesign) {
            isDisabled = true;
            disabledReason = 'Requires an active Taguchi design worksheet';
          } else if (item.pluginId === 'doe_analyze_factorial' && !hasFactorialDesign) {
            isDisabled = true;
            disabledReason = 'Requires an active Factorial design worksheet';
          } else if (item.pluginId === 'doe_analyze_rsm' && !hasRsmDesign) {
            isDisabled = true;
            disabledReason = 'Requires an active Response Surface (RSM) design worksheet';
          } else if (item.pluginId === 'doe_analyze_mixture' && !hasMixtureDesign) {
            isDisabled = true;
            disabledReason = 'Requires an active Mixture design worksheet';
          }

          return (
            <div key={item.id} className="fluent-cascade-item group">
              <button
                type="button"
                disabled={isDisabled}
                onClick={(e) => {
                  if (isDisabled) {
                    e.stopPropagation();
                    return;
                  }
                  if (!hasChildren) {
                    handleAction(item);
                  }
                }}
                className={`fluent-cascade-btn w-full px-3 py-1.5 text-left flex items-center justify-between transition-colors ${
                  isDisabled
                    ? 'opacity-40 cursor-not-allowed text-[#a19f9d] bg-transparent'
                    : 'cursor-pointer hover:bg-[#008450] hover:text-white'
                }`}
                title={disabledReason || item.label}
              >
                <div className="flex items-center space-x-2.5">
                  <span className="shrink-0 w-4.5 flex items-center justify-center">{getMenuOrPluginIcon(item.id, item.pluginId)}</span>
                  <span>{item.label}</span>
                </div>

                <div className="flex items-center space-x-2 pl-6">
                  {item.shortcut && (
                    <span className="text-[11px] text-[#605e5c] group-hover:text-white font-sans tracking-wide">
                      {item.shortcut}
                    </span>
                  )}
                  {hasChildren && <ChevronRightRegular className="w-3.5 h-3.5 text-[#605e5c]" />}
                </div>
              </button>

              {hasChildren && !isDisabled && (
                <div className="fluent-cascade-flyout">
                  {renderMenuItems(item.children!, depth + 1)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div
      ref={menuBarRef}
      className="flex items-center bg-[#f3f2f1] text-[#242424] px-1.5 py-0.5 border-b border-[#d2d0ce] select-none text-xs z-30 shadow-none"
    >
      {/* Root Menus (Menu Bar Mode: Hover transfers active state once open) */}
      <div className="flex items-center space-x-0.5">
        {menuTree.map((root) => {
          const isRootOpen = activeRootId === root.id;
          const hasChildren = Boolean(root.children && root.children.length > 0);

          return (
            <div key={root.id} className="relative">
              <button
                type="button"
                onClick={() => setActiveRootId(isRootOpen ? null : root.id)}
                onMouseEnter={() => {
                  if (activeRootId !== null && activeRootId !== root.id) {
                    setActiveRootId(root.id);
                  }
                }}
                className={`px-2.5 py-1 rounded transition-colors text-xs font-medium ${
                  isRootOpen
                    ? 'bg-[#008450] text-white shadow-xs'
                    : 'text-[#323130] hover:bg-[#e1dfdd]'
                }`}
              >
                {root.label}
              </button>

              {isRootOpen && hasChildren && renderMenuItems(root.children!)}
            </div>
          );
        })}
      </div>
    </div>
  );

};

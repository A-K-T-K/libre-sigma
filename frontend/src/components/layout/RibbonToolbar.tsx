import React from 'react';
import {
  Button,
} from '@fluentui/react-components';
import {
  DatabaseRegular,
  ArrowUploadRegular,
  ArrowDownloadRegular,
  AddSquareRegular,
  DeleteDismissRegular,
  TableAddRegular,
  DocumentAddRegular,
  ArrowSortRegular,
  ArrowUndoRegular,
  ArrowRedoRegular,
  SearchRegular,
} from '@fluentui/react-icons';
import { useWorksheetStore } from '../../store/useWorksheetStore';
import { useSessionStore } from '../../store/useSessionStore';
import { guardUnsavedChanges } from '../../hooks/useUnsavedGuard';

interface RibbonToolbarProps {
  onOpenSampleModal: () => void;
  onOpenImportCsvModal: () => void;
  onOpenCommandPalette?: () => void;
}

export const RibbonToolbar: React.FC<RibbonToolbarProps> = ({
  onOpenSampleModal,
  onOpenImportCsvModal,
  onOpenCommandPalette,
}) => {

  const { addRow, addColumn, activeSheetId, getActiveWorksheet, createSheet, clearSheet, undo, redo, _undoStack, _redoStack } = useWorksheetStore();
  const { clearSession } = useSessionStore();

  const handleExportCsv = () => {
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
  };

  return (
    <div className="flex items-center bg-[#f5f5f5] border-b border-[#e1dfdd] px-3 py-1 space-x-2 overflow-x-auto select-none text-xs shadow-2xs">
      {/* Group: Undo / Redo */}
      <div className="flex items-center space-x-0.5 pr-2 border-r border-[#d2d0ce]">
        <Button
          appearance="subtle"
          size="small"
          icon={<ArrowUndoRegular />}
          onClick={undo}
          disabled={_undoStack.length === 0}
          title="Undo (Ctrl+Z)"
        />
        <Button
          appearance="subtle"
          size="small"
          icon={<ArrowRedoRegular />}
          onClick={redo}
          disabled={_redoStack.length === 0}
          title="Redo (Ctrl+Y)"
        />
      </div>

      {/* Group: Data & File Presets */}
      <div className="flex items-center space-x-1 pr-2 border-r border-[#d2d0ce]">
        <Button
          appearance="primary"
          size="small"
          icon={<DatabaseRegular />}
          onClick={() => guardUnsavedChanges(onOpenSampleModal, 'loading a sample dataset', 'Open Sample Dataset')}
          title="Load curated sample datasets (Bearings, Chemical Yield, Pulse Study...)"
        >
          Sample Data
        </Button>

        <Button
          appearance="secondary"
          size="small"
          icon={<DocumentAddRegular />}
          onClick={() => createSheet()}
          title="Create a new blank worksheet"
        >
          New Worksheet
        </Button>

        <Button
          appearance="secondary"
          size="small"
          icon={<ArrowUploadRegular />}
          onClick={() => guardUnsavedChanges(onOpenImportCsvModal, 'importing CSV data', 'Import CSV')}
          title="Import CSV, TSV, or comma-separated files"
        >
          Import CSV
        </Button>

        <Button
          appearance="secondary"
          size="small"
          icon={<ArrowDownloadRegular />}
          onClick={handleExportCsv}
          title="Export active worksheet as CSV"
        >
          Export CSV
        </Button>
      </div>

      {/* Group: Worksheet Operations */}
      <div className="flex items-center space-x-1 pr-2 border-r border-[#d2d0ce]">
        <Button
          appearance="secondary"
          size="small"
          icon={<TableAddRegular />}
          onClick={() => activeSheetId && addColumn(activeSheetId)}
          title="Insert a new column to active sheet"
        >
          + Column
        </Button>

        <Button
          appearance="secondary"
          size="small"
          icon={<AddSquareRegular />}
          onClick={() => activeSheetId && addRow(activeSheetId)}
          title="Insert new rows to active sheet"
        >
          + Rows
        </Button>

        <Button
          appearance="subtle"
          size="small"
          icon={<DeleteDismissRegular />}
          onClick={() => activeSheetId && clearSheet(activeSheetId)}
          title="Clear all data in active worksheet"
        >
          Clear Sheet
        </Button>
      </div>

      {/* Group: Search & Command Palette */}
      <div className="flex items-center ml-auto space-x-1">
        {onOpenCommandPalette && (
          <button
            type="button"
            onClick={onOpenCommandPalette}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs bg-white hover:bg-[#faf9f8] border border-[#d2d0ce] rounded-md shadow-2xs text-[#605e5c] hover:text-[#201f1e] transition-colors cursor-pointer"
            title="Search all statistical tools, DOE designers, and commands (Ctrl+K)"
          >
            <SearchRegular className="w-3.5 h-3.5 text-[#008450]" />
            <span className="hidden sm:inline">Search tools...</span>
            <kbd className="px-1.5 py-0.2 text-[10px] bg-[#edebe9] rounded border border-[#d2d0ce] text-[#323130] font-sans">Ctrl+K</kbd>
          </button>
        )}
      </div>
    </div>
  );
};


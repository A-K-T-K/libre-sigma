import { create } from 'zustand';
import {
  ColumnDef,
  ColumnDataType,
  ColumnAnalyticalRole,
  Worksheet,
  PatternedDataConfig,
  SortKeyConfig,
  RecodeMapping,
  RecodeRangeRule,
  DoeDesignMeta
} from '../types';
import { evaluateWorksheetFormula, extractReferencedColumns } from '../utils/formulaEngine';
import { useSessionStore } from './useSessionStore';

interface WorksheetState {
  worksheets: Worksheet[];
  activeSheetId: string;
  selectedCell: { rowIdx: number; colId: string } | null;
  selectedRange: { startRow: number; endRow: number; startColId: string; endColId: string } | null;
  selectedColumnId: string | null;
  selectedRowIdx: number | null;

  // Actions
  createSheet: (name?: string, columns?: ColumnDef[], rows?: Record<string, any>[]) => string;
  deleteSheet: (sheetId: string) => void;
  renameSheet: (sheetId: string, name: string) => void;
  setActiveSheet: (sheetId: string) => void;
  setSelectedCell: (cell: { rowIdx: number; colId: string } | null) => void;
  setSelectedRange: (range: { startRow: number; endRow: number; startColId: string; endColId: string } | null) => void;
  setSelectedColumnId: (colId: string | null) => void;
  setSelectedRowIdx: (rowIdx: number | null) => void;

  setCell: (sheetId: string, rowIdx: number, colId: string, value: any) => void;
  setColumnName: (sheetId: string, colId: string, name: string) => void;
  setColumnType: (sheetId: string, colId: string, type: ColumnDataType) => void;
  setColumnRole: (sheetId: string, colId: string, role: ColumnAnalyticalRole) => void;
  setColumnFormula: (sheetId: string, colId: string, formula: string) => { success: boolean; error?: string };
  clearColumnFormula: (sheetId: string, colId: string) => void;
  setColumnWidth: (sheetId: string, colId: string, width: number) => void;

  addColumn: (sheetId: string, name?: string, type?: ColumnDataType, role?: ColumnAnalyticalRole) => string;
  deleteColumn: (sheetId: string, colId: string) => void;
  addRow: (sheetId: string) => void;
  deleteRow: (sheetId: string, rowIdx: number) => void;

  // Data Manipulation Suite
  createPatternedData: (sheetId: string, config: PatternedDataConfig) => void;
  sortWorksheet: (sheetId: string, sortKeys: SortKeyConfig[], selectedColsOnly?: boolean) => void;
  stackColumns: (sheetId: string, sourceColIds: string[], targetDataColName: string, targetSubscriptColName: string) => void;
  unstackColumns: (sheetId: string, responseColId: string, groupColId: string) => void;
  recodeColumn: (sheetId: string, sourceColId: string, targetColId: string, mappings: RecodeMapping[], rangeRules?: RecodeRangeRule[]) => void;
  subsetWorksheet: (sheetId: string, conditionColId: string, operator: string, compareValue: any, newSheetName?: string) => string;

  appendOutputColumns: (sheetId: string, newCols: Array<{ name: string; data: any[]; role?: ColumnAnalyticalRole; isLocked?: boolean }>) => void;
  appendColumns: (sheetId: string, newCols: ColumnDef[], newRowsData: Record<string, any>[]) => void;
  recalculateFormulas: (sheetId: string) => void;
  loadDataset: (name: string, columns: ColumnDef[], rows: Record<string, any>[], designMeta?: DoeDesignMeta) => void;
  pasteMatrix: (sheetId: string, startRow: number, startColIdx: number, matrix: string[][]) => void;
  clearSheet: (sheetId: string) => void;
  clearRange: (sheetId: string) => void;
  deleteCells: (sheetId: string) => void;
  copyCells: (sheetId: string) => Promise<void>;
  cutCells: (sheetId: string) => Promise<void>;
  pasteCells: (sheetId: string) => Promise<void>;

  // Undo / Redo
  _undoStack: Array<{ worksheets: Worksheet[]; activeSheetId: string }>;
  _redoStack: Array<{ worksheets: Worksheet[]; activeSheetId: string }>;
  _pushUndo: () => void;
  undo: () => void;
  redo: () => void;
  getActiveWorksheet: () => Worksheet | undefined;

  // Project state & dirty tracking
  isDirty: boolean;
  setIsDirty: (dirty: boolean) => void;
  createNewProject: () => void;
}

const generateDefaultColumns = (count = 12): ColumnDef[] => {
  return Array.from({ length: count }, (_, i) => ({
    id: `c${i + 1}`,
    name: '',
    type: 'numeric' as ColumnDataType,
    role: 'CONTINUOUS' as ColumnAnalyticalRole,
    width: 105,
  }));
};

const generateEmptyRows = (rowCount = 35): Record<string, any>[] => {
  return Array.from({ length: rowCount }, () => ({}));
};

const initialSampleColumns: ColumnDef[] = [
  { id: 'c1', name: 'Machine1', type: 'numeric', role: 'CONTINUOUS', width: 110 },
  { id: 'c2', name: 'Machine2', type: 'numeric', role: 'CONTINUOUS', width: 110 },
  { id: 'c3', name: 'Batch', type: 'text', role: 'CATEGORICAL', width: 110 },
  { id: 'c4', name: 'Machine_Diff', type: 'numeric', role: 'RESPONSE', formula: 'C2 - C1', isCalculated: true, width: 120 },
  { id: 'c5', name: '', type: 'numeric', role: 'CONTINUOUS', width: 105 },
  { id: 'c6', name: '', type: 'numeric', role: 'CONTINUOUS', width: 105 },
  { id: 'c7', name: '', type: 'numeric', role: 'CONTINUOUS', width: 105 },
  { id: 'c8', name: '', type: 'numeric', role: 'CONTINUOUS', width: 105 },
  { id: 'c9', name: '', type: 'numeric', role: 'CONTINUOUS', width: 105 },
  { id: 'c10', name: '', type: 'numeric', role: 'CONTINUOUS', width: 105 },
  { id: 'c11', name: '', type: 'numeric', role: 'CONTINUOUS', width: 105 },
  { id: 'c12', name: '', type: 'numeric', role: 'CONTINUOUS', width: 105 },
];

const initialSampleRows: Record<string, any>[] = [
  { c1: 1.498, c2: 1.502, c3: 'Batch-A', c4: 0.004 },
  { c1: 1.501, c2: 1.504, c3: 'Batch-A', c4: 0.003 },
  { c1: 1.499, c2: 1.501, c3: 'Batch-A', c4: 0.002 },
  { c1: 1.503, c2: 1.506, c3: 'Batch-A', c4: 0.003 },
  { c1: 1.497, c2: 1.503, c3: 'Batch-A', c4: 0.006 },
  { c1: 1.502, c2: 1.505, c3: 'Batch-B', c4: 0.003 },
  { c1: 1.500, c2: 1.502, c3: 'Batch-B', c4: 0.002 },
  { c1: 1.496, c2: 1.507, c3: 'Batch-B', c4: 0.011 },
  { c1: 1.504, c2: 1.504, c3: 'Batch-B', c4: 0.000 },
  { c1: 1.499, c2: 1.508, c3: 'Batch-B', c4: 0.009 },
  { c1: 1.501, c2: 1.503, c3: 'Batch-C', c4: 0.002 },
  { c1: 1.498, c2: 1.505, c3: 'Batch-C', c4: 0.007 },
  { c1: 1.502, c2: 1.506, c3: 'Batch-C', c4: 0.004 },
  { c1: 1.495, c2: 1.502, c3: 'Batch-C', c4: 0.007 },
  { c1: 1.500, c2: 1.504, c3: 'Batch-C', c4: 0.004 },
  { c1: 1.503, c2: 1.507, c3: 'Batch-D', c4: 0.004 },
  { c1: 1.497, c2: 1.505, c3: 'Batch-D', c4: 0.008 },
  { c1: 1.499, c2: 1.503, c3: 'Batch-D', c4: 0.004 },
  { c1: 1.502, c2: 1.506, c3: 'Batch-D', c4: 0.004 },
  { c1: 1.501, c2: 1.508, c3: 'Batch-D', c4: 0.007 },
  ...generateEmptyRows(15),
];

const initialSheet: Worksheet = {
  id: 'sheet-1',
  name: 'Worksheet 1',
  columns: initialSampleColumns,
  rows: initialSampleRows,
  autoRecalculateFormulas: true,
};

export const useWorksheetStore = create<WorksheetState>((set, get) => ({
  worksheets: [initialSheet],
  activeSheetId: 'sheet-1',
  selectedCell: { rowIdx: 0, colId: 'c1' },
  selectedRange: null,
  selectedColumnId: null,
  selectedRowIdx: null,

  isDirty: false,
  setIsDirty: (dirty: boolean) => set({ isDirty: dirty }),

  createNewProject: () => {
    const newSheet: Worksheet = {
      id: `sheet-${Date.now()}`,
      name: 'Worksheet 1',
      columns: generateDefaultColumns(12),
      rows: generateEmptyRows(35),
      autoRecalculateFormulas: true,
    };
    set({
      worksheets: [newSheet],
      activeSheetId: newSheet.id,
      selectedCell: { rowIdx: 0, colId: 'c1' },
      selectedRange: null,
      selectedColumnId: null,
      selectedRowIdx: null,
      _undoStack: [],
      _redoStack: [],
      isDirty: false,
    });
    useSessionStore.getState().clearSession();
    document.title = 'LibRE Tab - Untitled Project';
  },

  _undoStack: [],
  _redoStack: [],

  _pushUndo: () => {
    const { worksheets, activeSheetId, _undoStack } = get();
    const snapshot = {
      worksheets: JSON.parse(JSON.stringify(worksheets)),
      activeSheetId,
    };
    const newStack = [..._undoStack, snapshot];
    if (newStack.length > 50) newStack.shift();
    set({ _undoStack: newStack, _redoStack: [], isDirty: true });
  },

  undo: () => {
    const { _undoStack, _redoStack, worksheets, activeSheetId } = get();
    if (_undoStack.length === 0) return;
    const prev = _undoStack[_undoStack.length - 1];
    const currentSnapshot = {
      worksheets: JSON.parse(JSON.stringify(worksheets)),
      activeSheetId,
    };
    set({
      worksheets: prev.worksheets,
      activeSheetId: prev.activeSheetId,
      _undoStack: _undoStack.slice(0, -1),
      _redoStack: [..._redoStack, currentSnapshot],
      isDirty: true,
    });
  },

  redo: () => {
    const { _undoStack, _redoStack, worksheets, activeSheetId } = get();
    if (_redoStack.length === 0) return;
    const next = _redoStack[_redoStack.length - 1];
    const currentSnapshot = {
      worksheets: JSON.parse(JSON.stringify(worksheets)),
      activeSheetId,
    };
    set({
      worksheets: next.worksheets,
      activeSheetId: next.activeSheetId,
      _undoStack: [..._undoStack, currentSnapshot],
      _redoStack: _redoStack.slice(0, -1),
      isDirty: true,
    });
  },

  getActiveWorksheet: () => {
    const { worksheets, activeSheetId } = get();
    return worksheets.find((w) => w.id === activeSheetId) || worksheets[0];
  },

  createSheet: (name, columns, rows) => {
    get()._pushUndo();
    const { worksheets } = get();
    const sheetNum = worksheets.length + 1;
    const newId = `sheet-${Date.now()}`;
    const newSheet: Worksheet = {
      id: newId,
      name: name || `Worksheet ${sheetNum}`,
      columns: columns || generateDefaultColumns(12),
      rows: rows || generateEmptyRows(35),
      autoRecalculateFormulas: true,
    };

    set({
      worksheets: [...worksheets, newSheet],
      activeSheetId: newId,
      selectedCell: { rowIdx: 0, colId: newSheet.columns[0]?.id || 'c1' },
      selectedRange: null,
      selectedColumnId: null,
      selectedRowIdx: null,
    });

    return newId;
  },

  deleteSheet: (sheetId) => {
    get()._pushUndo();
    const { worksheets, activeSheetId } = get();
    if (worksheets.length <= 1) return;
    const nextWorksheets = worksheets.filter((w) => w.id !== sheetId);
    const nextActiveId = activeSheetId === sheetId ? nextWorksheets[0].id : activeSheetId;
    set({ worksheets: nextWorksheets, activeSheetId: nextActiveId });
  },

  renameSheet: (sheetId, name) => {
    get()._pushUndo();
    set((state) => ({
      worksheets: state.worksheets.map((w) => (w.id === sheetId ? { ...w, name } : w)),
    }));
  },

  setActiveSheet: (sheetId) => {
    set({
      activeSheetId: sheetId,
      selectedCell: { rowIdx: 0, colId: 'c1' },
      selectedRange: null,
      selectedColumnId: null,
      selectedRowIdx: null,
    });
  },

  setSelectedCell: (cell) => {
    set({ selectedCell: cell, selectedColumnId: null, selectedRowIdx: null });
  },

  setSelectedRange: (range) => {
    set({ selectedRange: range });
  },

  setSelectedColumnId: (colId) => {
    set({ selectedColumnId: colId, selectedRowIdx: null, selectedCell: colId ? { rowIdx: 0, colId } : null });
  },

  setSelectedRowIdx: (rowIdx) => {
    set({ selectedRowIdx: rowIdx, selectedColumnId: null, selectedCell: rowIdx !== null ? { rowIdx, colId: 'c1' } : null });
  },

  setCell: (sheetId, rowIdx, colId, value) => {
    // Only push undo state if we are done editing (debounce this or handle on commit)
    // For now, we keep it but it could be optimized out of keystroke handlers
    get()._pushUndo();
    set((state) => {
      const nextWorksheets = state.worksheets.map((w) => {
        if (w.id !== sheetId) return w;
        const newRows = [...w.rows];
        while (newRows.length <= rowIdx) {
          newRows.push({});
        }
        newRows[rowIdx] = { ...newRows[rowIdx], [colId]: value };

        // Fast O(1) incremental type inferencing
        let columnsChanged = false;
        const newCols = w.columns.map((c) => {
          if (c.id !== colId) return c;
          
          const isEmpty = value === null || value === undefined || value === '';
          if (isEmpty) return c; // Don't change type for empty values
          
          const isNumericVal = !isNaN(Number(value));
          const isDateVal = !isNaN(Date.parse(String(value))) && isNaN(Number(value));
          
          let inferredType: ColumnDataType = c.type;
          
          // If column was numeric, but we just typed a non-numeric string, downgrade to text
          if (c.type === 'numeric' && !isNumericVal) {
             inferredType = isDateVal ? 'date' : 'text';
          }
          // If column was date, but we just typed a non-date string, downgrade to text
          else if (c.type === 'date' && !isDateVal) {
             inferredType = isNumericVal ? 'numeric' : 'text';
          }
          // If column was text, we don't auto-upgrade to numeric on a single cell to avoid flapping,
          // unless the user forces a column type cast manually.

          if (c.type !== inferredType) {
             columnsChanged = true;
             return { ...c, type: inferredType };
          }
          return c;
        });

        return { ...w, columns: columnsChanged ? newCols : w.columns, rows: newRows };
      });

      return { worksheets: nextWorksheets };
    });

    // Auto-recalculate any calculated formula columns
    get().recalculateFormulas(sheetId);
  },

  setColumnName: (sheetId, colId, name) => {
    get()._pushUndo();
    set((state) => ({
      worksheets: state.worksheets.map((w) => {
        if (w.id !== sheetId) return w;
        return {
          ...w,
          columns: w.columns.map((c) => (c.id === colId ? { ...c, name } : c)),
        };
      }),
    }));
  },

  setColumnType: (sheetId, colId, type) => {
    get()._pushUndo();
    set((state) => ({
      worksheets: state.worksheets.map((w) => {
        if (w.id !== sheetId) return w;
        return {
          ...w,
          columns: w.columns.map((c) => (c.id === colId ? { ...c, type } : c)),
        };
      }),
    }));
  },

  setColumnRole: (sheetId, colId, role) => {
    get()._pushUndo();
    set((state) => ({
      worksheets: state.worksheets.map((w) => {
        if (w.id !== sheetId) return w;
        return {
          ...w,
          columns: w.columns.map((c) => (c.id === colId ? { ...c, role } : c)),
        };
      }),
    }));
  },

  setColumnWidth: (sheetId, colId, width) => {
    get()._pushUndo();
    set((state) => ({
      worksheets: state.worksheets.map((w) => {
        if (w.id !== sheetId) return w;
        return {
          ...w,
          columns: w.columns.map((c) => (c.id === colId ? { ...c, width } : c)),
        };
      }),
    }));
  },

  setColumnFormula: (sheetId, colId, formula) => {
    const sheet = get().worksheets.find((w) => w.id === sheetId);
    if (!sheet) return { success: false, error: 'Worksheet not found' };
    get()._pushUndo();

    const evalRes = evaluateWorksheetFormula(formula, sheet.columns, sheet.rows);
    if (!evalRes.success || !evalRes.values) {
      return { success: false, error: evalRes.errorMessage || 'Invalid formula' };
    }

    set((state) => ({
      worksheets: state.worksheets.map((w) => {
        if (w.id !== sheetId) return w;
        const newRows = w.rows.map((row, idx) => ({
          ...row,
          [colId]: evalRes.values![idx],
        }));

        const newCols = w.columns.map((c) =>
          c.id === colId
            ? { ...c, formula, isCalculated: true, type: 'numeric' as ColumnDataType }
            : c
        );

        return { ...w, columns: newCols, rows: newRows };
      }),
    }));

    return { success: true };
  },

  clearColumnFormula: (sheetId, colId) => {
    get()._pushUndo();
    set((state) => ({
      worksheets: state.worksheets.map((w) => {
        if (w.id !== sheetId) return w;
        return {
          ...w,
          columns: w.columns.map((c) =>
            c.id === colId ? { ...c, formula: undefined, isCalculated: false } : c
          ),
        };
      }),
    }));
  },

  recalculateFormulas: (sheetId) => {
    const sheet = get().worksheets.find((w) => w.id === sheetId);
    if (!sheet || sheet.autoRecalculateFormulas === false) return;

    const calcCols = sheet.columns.filter((c) => c.isCalculated && c.formula);
    if (calcCols.length === 0) return;

    set((state) => ({
      worksheets: state.worksheets.map((w) => {
        if (w.id !== sheetId) return w;
        let nextRows = [...w.rows];

        calcCols.forEach((col) => {
          if (col.formula) {
            const evalRes = evaluateWorksheetFormula(col.formula, w.columns, nextRows);
            if (evalRes.success && evalRes.values) {
              nextRows = nextRows.map((r, idx) => ({
                ...r,
                [col.id]: evalRes.values![idx],
              }));
            }
          }
        });

        return { ...w, rows: nextRows };
      }),
    }));
  },

  addColumn: (sheetId, name, type = 'numeric', role = 'CONTINUOUS') => {
    const { worksheets } = get();
    const sheet = worksheets.find((w) => w.id === sheetId);
    if (!sheet) return '';
    get()._pushUndo();

    const newIndex = sheet.columns.length + 1;
    const newColId = `c${newIndex}`;
    const newCol: ColumnDef = {
      id: newColId,
      name: name || '',
      type,
      role,
      width: 105,
    };

    set({
      worksheets: worksheets.map((w) =>
        w.id === sheetId ? { ...w, columns: [...w.columns, newCol] } : w
      ),
    });

    return newColId;
  },

  deleteColumn: (sheetId, colId) => {
    get()._pushUndo();
    set((state) => ({
      worksheets: state.worksheets.map((w) => {
        if (w.id !== sheetId) return w;
        if (w.columns.length <= 1) return w;
        const newCols = w.columns.filter((c) => c.id !== colId);
        const newRows = w.rows.map((r) => {
          const newR = { ...r };
          delete newR[colId];
          return newR;
        });
        return { ...w, columns: newCols, rows: newRows };
      }),
    }));
  },

  addRow: (sheetId) => {
    get()._pushUndo();
    set((state) => ({
      worksheets: state.worksheets.map((w) => {
        if (w.id !== sheetId) return w;
        return { ...w, rows: [...w.rows, ...generateEmptyRows(5)] };
      }),
    }));
  },

  deleteRow: (sheetId, rowIdx) => {
    get()._pushUndo();
    set((state) => ({
      worksheets: state.worksheets.map((w) => {
        if (w.id !== sheetId) return w;
        const newRows = w.rows.filter((_, idx) => idx !== rowIdx);
        return { ...w, rows: newRows.length > 0 ? newRows : generateEmptyRows(1) };
      }),
    }));
  },

  // -------------------------------------------------------------
  // Data Manipulation & Transformation Suite
  // -------------------------------------------------------------
  createPatternedData: (sheetId, config) => {
    const sheet = get().worksheets.find((w) => w.id === sheetId);
    if (!sheet) return;
    get()._pushUndo();

    let baseSequence: (number | string)[] = [];
    if (config.type === 'numeric') {
      const from = config.from ?? 1;
      const to = config.to ?? 10;
      const by = config.by ?? 1;
      if (by > 0 && to >= from) {
        for (let v = from; v <= to; v += by) {
          baseSequence.push(Number(v.toFixed(6)));
        }
      } else if (by < 0 && to <= from) {
        for (let v = from; v >= to; v += by) {
          baseSequence.push(Number(v.toFixed(6)));
        }
      }
    } else {
      baseSequence = config.textValues && config.textValues.length > 0 ? config.textValues : ['A', 'B'];
    }

    const itemRepeats = Math.max(1, config.repeatEachValue || 1);
    const wholeRepeats = Math.max(1, config.repeatWholeSeq || 1);

    const fullSequence: (number | string)[] = [];
    for (let w = 0; w < wholeRepeats; w++) {
      for (const item of baseSequence) {
        for (let k = 0; k < itemRepeats; k++) {
          fullSequence.push(item);
        }
      }
    }

    set((state) => ({
      worksheets: state.worksheets.map((ws) => {
        if (ws.id !== sheetId) return ws;
        const targetCol = ws.columns.find((c) => c.id === config.targetColId);
        const rowsNeeded = Math.max(ws.rows.length, fullSequence.length);
        const nextRows = Array.from({ length: rowsNeeded }, (_, idx) => {
          const existing = ws.rows[idx] || {};
          return {
            ...existing,
            [config.targetColId]: idx < fullSequence.length ? fullSequence[idx] : existing[config.targetColId],
          };
        });

        const nextCols = ws.columns.map((c) =>
          c.id === config.targetColId
            ? { ...c, type: config.type === 'numeric' ? ('numeric' as ColumnDataType) : ('text' as ColumnDataType) }
            : c
        );

        return { ...ws, columns: nextCols, rows: nextRows };
      }),
    }));
  },

  sortWorksheet: (sheetId, sortKeys, selectedColsOnly = false) => {
    get()._pushUndo();
    set((state) => ({
      worksheets: state.worksheets.map((ws) => {
        if (ws.id !== sheetId || sortKeys.length === 0) return ws;

        const rowsWithIndex = ws.rows.map((r, i) => ({ ...r, __origIdx: i }));

        rowsWithIndex.sort((a: any, b: any) => {
          for (const key of sortKeys) {
            const valA = a[key.colId];
            const valB = b[key.colId];

            if (valA === undefined || valA === null || valA === '') {
              if (valB === undefined || valB === null || valB === '') continue;
              return 1; // Empty values to bottom
            }
            if (valB === undefined || valB === null || valB === '') return -1;

            const numA = Number(valA);
            const numB = Number(valB);
            const isBothNum = !isNaN(numA) && !isNaN(numB);

            let comp = 0;
            if (isBothNum) {
              comp = numA - numB;
            } else {
              comp = String(valA).localeCompare(String(valB));
            }

            if (comp !== 0) {
              return key.direction === 'asc' ? comp : -comp;
            }
          }
          return a.__origIdx - b.__origIdx;
        });

        const sortedRows = rowsWithIndex.map(({ __origIdx, ...rest }) => rest);
        return { ...ws, rows: sortedRows };
      }),
    }));
  },

  stackColumns: (sheetId, sourceColIds, targetDataColName, targetSubscriptColName) => {
    const sheet = get().worksheets.find((w) => w.id === sheetId);
    if (!sheet || sourceColIds.length < 2) return;

    const sourceCols = sheet.columns.filter((c) => sourceColIds.includes(c.id));
    const stackedData: any[] = [];
    const subscriptData: string[] = [];

    sourceCols.forEach((col) => {
      const label = col.name || col.id.toUpperCase();
      sheet.rows.forEach((r) => {
        const val = r[col.id];
        if (val !== undefined && val !== null && val !== '') {
          stackedData.push(val);
          subscriptData.push(label);
        }
      });
    });

    const newSheetName = `${sheet.name} (Stacked)`;
    const newCol1: ColumnDef = { id: 'c1', name: targetDataColName || 'Response_Stacked', type: 'numeric', role: 'RESPONSE' };
    const newCol2: ColumnDef = { id: 'c2', name: targetSubscriptColName || 'Subscript_Group', type: 'text', role: 'CATEGORICAL' };
    const otherCols = generateDefaultColumns(10).map((c, i) => ({ ...c, id: `c${i + 3}` }));

    const newRows: Record<string, any>[] = stackedData.map((d, idx) => ({
      c1: d,
      c2: subscriptData[idx],
    }));

    get().createSheet(newSheetName, [newCol1, newCol2, ...otherCols], newRows);
  },

  unstackColumns: (sheetId, responseColId, groupColId) => {
    const sheet = get().worksheets.find((w) => w.id === sheetId);
    if (!sheet) return;

    const groups = Array.from(new Set(sheet.rows.map((r) => r[groupColId]).filter((v) => v !== undefined && v !== null && v !== '')));
    if (groups.length < 1) return;

    const groupedData: Record<string, any[]> = {};
    groups.forEach((g) => { groupedData[String(g)] = []; });

    sheet.rows.forEach((r) => {
      const gVal = r[groupColId];
      const yVal = r[responseColId];
      if (gVal !== undefined && gVal !== null && gVal !== '' && yVal !== undefined && yVal !== null) {
        groupedData[String(gVal)].push(yVal);
      }
    });

    const newCols: ColumnDef[] = groups.map((g, idx) => ({
      id: `c${idx + 1}`,
      name: String(g),
      type: 'numeric',
      role: 'CONTINUOUS',
    }));

    const maxLen = Math.max(...Object.values(groupedData).map((arr) => arr.length));
    const newRows: Record<string, any>[] = Array.from({ length: maxLen }, (_, rIdx) => {
      const rowObj: Record<string, any> = {};
      groups.forEach((g, cIdx) => {
        rowObj[`c${cIdx + 1}`] = groupedData[String(g)][rIdx] ?? null;
      });
      return rowObj;
    });

    const padCols = generateDefaultColumns(10).map((c, i) => ({ ...c, id: `c${i + newCols.length + 1}` }));
    get().createSheet(`${sheet.name} (Unstacked)`, [...newCols, ...padCols], newRows);
  },

  recodeColumn: (sheetId, sourceColId, targetColId, mappings, rangeRules) => {
    get()._pushUndo();
    set((state) => ({
      worksheets: state.worksheets.map((ws) => {
        if (ws.id !== sheetId) return ws;

        const nextRows = ws.rows.map((row) => {
          const curVal = row[sourceColId];
          if (curVal === undefined || curVal === null || curVal === '') return row;

          let recoded = curVal;

          // Exact string match mapping
          const mapHit = mappings.find((m) => String(m.fromValue).trim() === String(curVal).trim());
          if (mapHit) {
            recoded = mapHit.toValue;
          } else if (rangeRules && !isNaN(Number(curVal))) {
            const num = Number(curVal);
            for (const rule of rangeRules) {
              const minOk = rule.minVal === undefined || num >= rule.minVal;
              const maxOk = rule.maxVal === undefined || num <= rule.maxVal;
              if (minOk && maxOk) {
                recoded = rule.toValue;
                break;
              }
            }
          }

          return { ...row, [targetColId]: recoded };
        });

        return { ...ws, rows: nextRows };
      }),
    }));
  },

  subsetWorksheet: (sheetId, conditionColId, operator, compareValue, newSheetName) => {
    const sheet = get().worksheets.find((w) => w.id === sheetId);
    if (!sheet) return '';

    const filteredRows = sheet.rows.filter((r) => {
      const val = r[conditionColId];
      if (val === undefined || val === null || val === '') return false;

      const numVal = Number(val);
      const compNum = Number(compareValue);
      const isNum = !isNaN(numVal) && !isNaN(compNum);

      switch (operator) {
        case '>': return isNum ? numVal > compNum : String(val) > String(compareValue);
        case '>=': return isNum ? numVal >= compNum : String(val) >= String(compareValue);
        case '<': return isNum ? numVal < compNum : String(val) < String(compareValue);
        case '<=': return isNum ? numVal <= compNum : String(val) <= String(compareValue);
        case '==': return String(val).trim() === String(compareValue).trim();
        case '!=': return String(val).trim() !== String(compareValue).trim();
        default: return true;
      }
    });

    const finalSheetName = newSheetName || `${sheet.name} (Subset)`;
    return get().createSheet(finalSheetName, sheet.columns, filteredRows);
  },

  // -------------------------------------------------------------
  // Statistical Storage Engine: Residuals, Fits, PCA Scores, Runs
  // -------------------------------------------------------------
  appendOutputColumns: (sheetId, newColsData) => {
    get()._pushUndo();
    set((state) => ({
      worksheets: state.worksheets.map((ws) => {
        if (ws.id !== sheetId) return ws;

        let curCols = [...ws.columns];
        let nextRows = [...ws.rows];

        newColsData.forEach((item) => {
          const newIndex = curCols.length + 1;
          const newColId = `c${newIndex}`;
          const newColDef: ColumnDef = {
            id: newColId,
            name: item.name,
            type: 'numeric',
            role: item.role || 'RESIDUALS',
            isLocked: Boolean(item.isLocked),
            width: 110,
          };
          curCols.push(newColDef);

          const maxLen = Math.max(nextRows.length, item.data.length);
          while (nextRows.length < maxLen) {
            nextRows.push({});
          }

          nextRows = nextRows.map((r, rIdx) => ({
            ...r,
            [newColId]: rIdx < item.data.length ? item.data[rIdx] : null,
          }));
        });

        return { ...ws, columns: curCols, rows: nextRows };
      }),
    }));
  },

  appendColumns: (sheetId, newCols, newRowsData) => {
    get()._pushUndo();
    set((state) => ({
      worksheets: state.worksheets.map((ws) => {
        if (ws.id !== sheetId) return ws;
        const curCols = [...ws.columns, ...newCols];
        const nextRows = ws.rows.map((r, idx) => ({
          ...r,
          ...(newRowsData[idx] || {}),
        }));
        return { ...ws, columns: curCols, rows: nextRows };
      }),
    }));
  },

  loadDataset: (name, columns, rows, designMeta) => {
    const sheetId = get().createSheet(name, columns, rows);
    if (designMeta) {
      set((state) => ({
        worksheets: state.worksheets.map((w) =>
          w.id === sheetId ? { ...w, designMeta } : w
        ),
      }));
    }
  },

  pasteMatrix: (sheetId, startRow, startColIdx, matrix) => {
    get()._pushUndo();
    set((state) => ({
      worksheets: state.worksheets.map((w) => {
        if (w.id !== sheetId) return w;

        let newCols = [...w.columns];
        const neededCols = startColIdx + matrix[0].length;
        while (newCols.length < neededCols) {
          const nextIdx = newCols.length + 1;
          newCols.push({ id: `c${nextIdx}`, name: '', type: 'numeric', role: 'CONTINUOUS', width: 105 });
        }

        let newRows = [...w.rows];
        const neededRows = startRow + matrix.length;
        while (newRows.length < neededRows) {
          newRows.push({});
        }

        matrix.forEach((r, rOffset) => {
          const targetRowIdx = startRow + rOffset;
          const updatedRow = { ...newRows[targetRowIdx] };
          r.forEach((cellVal, cOffset) => {
            const colId = newCols[startColIdx + cOffset].id;
            const parsedNum = Number(cellVal);
            updatedRow[colId] = cellVal.trim() === '' ? null : !isNaN(parsedNum) ? parsedNum : cellVal.trim();
          });
          newRows[targetRowIdx] = updatedRow;
        });

        return { ...w, columns: newCols, rows: newRows };
      }),
    }));

    get().recalculateFormulas(sheetId);
  },

  clearSheet: (sheetId) => {
    get()._pushUndo();
    set((state) => ({
      worksheets: state.worksheets.map((w) => {
        if (w.id !== sheetId) return w;
        return {
          ...w,
          columns: generateDefaultColumns(12),
          rows: generateEmptyRows(35),
        };
      }),
    }));
  },

  clearRange: (sheetId) => {
    get()._pushUndo();
    const { selectedRange, selectedCell, selectedColumnId, selectedRowIdx } = get();
    set((state) => ({
      worksheets: state.worksheets.map((w) => {
        if (w.id !== sheetId) return w;

        let nextRows = [...w.rows];
        if (selectedRange) {
          const { startRow, endRow, startColId, endColId } = selectedRange;
          const colIndices = w.columns.map((c) => c.id);
          const c1 = colIndices.indexOf(startColId);
          const c2 = colIndices.indexOf(endColId);
          const minC = Math.min(c1, c2);
          const maxC = Math.max(c1, c2);
          const minR = Math.min(startRow, endRow);
          const maxR = Math.max(startRow, endRow);

          for (let r = minR; r <= maxR; r++) {
            if (nextRows[r]) {
              const updated = { ...nextRows[r] };
              for (let c = minC; c <= maxC; c++) {
                delete updated[colIndices[c]];
              }
              nextRows[r] = updated;
            }
          }
        } else if (selectedColumnId) {
          nextRows = nextRows.map((r) => {
            const nextR = { ...r };
            delete nextR[selectedColumnId];
            return nextR;
          });
        } else if (selectedRowIdx !== null) {
          nextRows[selectedRowIdx] = {};
        } else if (selectedCell) {
          if (nextRows[selectedCell.rowIdx]) {
            const nextR = { ...nextRows[selectedCell.rowIdx] };
            delete nextR[selectedCell.colId];
            nextRows[selectedCell.rowIdx] = nextR;
          }
        }

        return { ...w, rows: nextRows };
      }),
    }));
  },

  deleteCells: (sheetId: string) => {
    get()._pushUndo();
    const { selectedColumnId, selectedRowIdx, selectedRange, selectedCell, worksheets } = get();
    const ws = worksheets.find((w) => w.id === sheetId);
    if (!ws) return;

    if (selectedColumnId) {
      get().deleteColumn(sheetId, selectedColumnId);
    } else if (selectedRowIdx !== null) {
      get().deleteRow(sheetId, selectedRowIdx);
    } else if (selectedRange) {
      const minR = Math.min(selectedRange.startRow, selectedRange.endRow);
      const maxR = Math.max(selectedRange.startRow, selectedRange.endRow);
      set((state) => ({
        worksheets: state.worksheets.map((w) => {
          if (w.id !== sheetId) return w;
          const newRows = w.rows.filter((_, idx) => idx < minR || idx > maxR);
          return { ...w, rows: newRows.length > 0 ? newRows : generateEmptyRows(1) };
        }),
      }));
    } else if (selectedCell) {
      get().deleteRow(sheetId, selectedCell.rowIdx);
    }
  },

  copyCells: async (sheetId: string) => {
    const { selectedRange, selectedCell, selectedColumnId, selectedRowIdx, worksheets } = get();
    const ws = worksheets.find((w) => w.id === sheetId);
    if (!ws) return;

    let textToCopy = '';
    const cols = ws.columns;
    const colIds = cols.map((c) => c.id);

    if (selectedRange) {
      const minR = Math.min(selectedRange.startRow, selectedRange.endRow);
      const maxR = Math.max(selectedRange.startRow, selectedRange.endRow);
      const c1 = colIds.indexOf(selectedRange.startColId);
      const c2 = colIds.indexOf(selectedRange.endColId);
      const minC = Math.min(c1, c2);
      const maxC = Math.max(c1, c2);

      const lines: string[] = [];
      for (let r = minR; r <= maxR; r++) {
        const rowVals: string[] = [];
        for (let c = minC; c <= maxC; c++) {
          const val = ws.rows[r]?.[colIds[c]];
          rowVals.push(val !== undefined && val !== null ? String(val) : '');
        }
        lines.push(rowVals.join('\t'));
      }
      textToCopy = lines.join('\n');
    } else if (selectedColumnId) {
      const lines = ws.rows.map((r) => {
        const val = r[selectedColumnId];
        return val !== undefined && val !== null ? String(val) : '';
      });
      textToCopy = lines.join('\n');
    } else if (selectedRowIdx !== null) {
      const r = ws.rows[selectedRowIdx] || {};
      textToCopy = cols.map((c) => (r[c.id] !== undefined && r[c.id] !== null ? String(r[c.id]) : '')).join('\t');
    } else if (selectedCell) {
      const val = ws.rows[selectedCell.rowIdx]?.[selectedCell.colId];
      textToCopy = val !== undefined && val !== null ? String(val) : '';
    }

    if (textToCopy && navigator?.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(textToCopy);
      } catch (err) {
        console.warn('Clipboard write failed', err);
      }
    }
  },

  cutCells: async (sheetId: string) => {
    await get().copyCells(sheetId);
    get().clearRange(sheetId);
  },

  pasteCells: async (sheetId: string) => {
    if (!navigator?.clipboard?.readText) return;
    try {
      const text = await navigator.clipboard.readText();
      if (!text) return;
      const lines = text.split(/\r?\n/).map((line) => line.split('\t'));
      const { selectedCell, selectedRange, selectedColumnId, selectedRowIdx, worksheets } = get();
      const ws = worksheets.find((w) => w.id === sheetId);
      if (!ws) return;

      let startRow = 0;
      let startColIdx = 0;

      if (selectedCell) {
        startRow = selectedCell.rowIdx;
        startColIdx = Math.max(0, ws.columns.findIndex((c) => c.id === selectedCell.colId));
      } else if (selectedRange) {
        startRow = Math.min(selectedRange.startRow, selectedRange.endRow);
        startColIdx = Math.max(0, ws.columns.findIndex((c) => c.id === selectedRange.startColId));
      } else if (selectedRowIdx !== null) {
        startRow = selectedRowIdx;
        startColIdx = 0;
      } else if (selectedColumnId) {
        startRow = 0;
        startColIdx = Math.max(0, ws.columns.findIndex((c) => c.id === selectedColumnId));
      }

      get().pasteMatrix(sheetId, startRow, startColIdx, lines);
    } catch (err) {
      console.warn('Clipboard read failed', err);
    }
  },
}));

import React, { useCallback, useMemo, useRef, useState, useEffect } from 'react';
import DataEditor, {
  GridCell,
  GridCellKind,
  GridColumn,
  Item,
  EditableGridCell,
  CompactSelection,
  Rectangle,
  GridSelection,
  Theme,
} from '@glideapps/glide-data-grid';
import '@glideapps/glide-data-grid/dist/index.css';
import {
  ChevronRightRegular,
  CheckmarkRegular,
  DeleteRegular,
  AddRegular,
  ArrowSortRegular,
  LockClosedRegular,
  LockOpenRegular,
  EraserRegular,
  EditRegular,
} from '@fluentui/react-icons';
import { useWorksheetStore } from '../../store/useWorksheetStore';
import { ColumnDef, ColumnDataType, ColumnAnalyticalRole } from '../../types';

/** Minitab-style theme for Glide Data Grid */
const minitabTheme: Partial<Theme> = {
  accentColor: '#008450',
  accentLight: 'rgba(0,132,80,0.1)',
  accentFg: '#ffffff',
  bgCell: '#ffffff',
  bgCellMedium: '#fafaf9',
  bgHeader: '#efefef',
  bgHeaderHasFocus: '#e2e2e2',
  bgHeaderHovered: '#e2e2e2',
  textHeader: '#1b1b1b',
  textGroupHeader: '#444',
  textDark: '#1b1b1b',
  textMedium: '#444',
  textLight: '#888',
  borderColor: '#d0d0d0',
  drilldownBorder: '#008450',
  linkColor: '#0f6cbd',
  headerFontStyle: '600 12px "Segoe UI", system-ui, sans-serif',
  baseFontStyle: '13px "Segoe UI", system-ui, sans-serif',
  editorFontSize: '13px',
  fontFamily: '"Segoe UI", system-ui, -apple-system, sans-serif',
  cellHorizontalPadding: 6,
  cellVerticalPadding: 3,
};

export const WorksheetGrid: React.FC = () => {
  const activeSheetId = useWorksheetStore((state) => state.activeSheetId);
  const sheet = useWorksheetStore(
    useCallback((state) => state.worksheets.find((w) => w.id === state.activeSheetId), [])
  );
  const setCell = useWorksheetStore((state) => state.setCell);
  const setColumnName = useWorksheetStore((state) => state.setColumnName);
  const setColumnWidth = useWorksheetStore((state) => state.setColumnWidth);
  const setColumnType = useWorksheetStore((state) => state.setColumnType);
  const setColumnRole = useWorksheetStore((state) => state.setColumnRole);
  const addColumn = useWorksheetStore((state) => state.addColumn);
  const addRow = useWorksheetStore((state) => state.addRow);
  const deleteRow = useWorksheetStore((state) => state.deleteRow);
  const deleteColumn = useWorksheetStore((state) => state.deleteColumn);
  const sortWorksheet = useWorksheetStore((state) => state.sortWorksheet);
  const pasteMatrix = useWorksheetStore((state) => state.pasteMatrix);
  const setSelectedColumnId = useWorksheetStore((state) => state.setSelectedColumnId);
  const setSelectedRowIdx = useWorksheetStore((state) => state.setSelectedRowIdx);
  const setSelectedCell = useWorksheetStore((state) => state.setSelectedCell);

  const gridRef = useRef<any>(null);

  // ──────────────────────────────────────────────────────────────
  // Inline column-name editor (floated absolutely over header)
  // ──────────────────────────────────────────────────────────────
  const [headerEdit, setHeaderEdit] = useState<{
    colIdx: number;
    colId: string;
    value: string;
    rect: { x: number; y: number; w: number; h: number };
  } | null>(null);
  const headerInputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (headerEdit) {
      requestAnimationFrame(() => {
        headerInputRef.current?.focus();
        headerInputRef.current?.select();
      });
    }
  }, [headerEdit?.colIdx]);

  // ──────────────────────────────────────────────────────────────
  // Right-Click Context Menu State & Global Pointer Tracking
  // ──────────────────────────────────────────────────────────────
  const [contextMenu, setContextMenu] = useState<{
    type: 'header' | 'cell';
    colIdx: number;
    rowIdx?: number;
    x: number;
    y: number;
  } | null>(null);

  const gridWrapperRef = useRef<HTMLDivElement>(null);
  const lastMousePos = useRef<{ clientX: number; clientY: number }>({ clientX: 0, clientY: 0 });

  // Track global pointer position so right-click is pixel-accurate anywhere on the canvas
  useEffect(() => {
    const trackPointer = (e: MouseEvent) => {
      lastMousePos.current = { clientX: e.clientX, clientY: e.clientY };
    };
    window.addEventListener('pointermove', trackPointer, { passive: true });
    window.addEventListener('pointerdown', trackPointer, { capture: true, passive: true });
    window.addEventListener('contextmenu', trackPointer, { capture: true, passive: true });
    return () => {
      window.removeEventListener('pointermove', trackPointer);
      window.removeEventListener('pointerdown', trackPointer);
      window.removeEventListener('contextmenu', trackPointer);
    };
  }, []);

  // Dismiss context menu on click outside or escape key
  useEffect(() => {
    if (!contextMenu) return;
    const handleDismiss = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent && e.key !== 'Escape') return;
      setContextMenu(null);
    };
    const timer = setTimeout(() => {
      window.addEventListener('click', handleDismiss);
      window.addEventListener('contextmenu', handleDismiss);
      window.addEventListener('keydown', handleDismiss);
    }, 60);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('click', handleDismiss);
      window.removeEventListener('contextmenu', handleDismiss);
      window.removeEventListener('keydown', handleDismiss);
    };
  }, [contextMenu]);

  // ──────────────────────────────────────────────────────────────
  // Grid selection state (controlled)
  // ──────────────────────────────────────────────────────────────
  const [gridSelection, setGridSelection] = useState<GridSelection>({
    columns: CompactSelection.empty(),
    rows: CompactSelection.empty(),
    current: undefined,
  });

  const totalRows = sheet?.rows.length ?? 0;

  // ──────────────────────────────────────────────────────────────
  // Columns: two-tier header (group = C1/C2-T, title = var name)
  // ──────────────────────────────────────────────────────────────
  const gridColumns: GridColumn[] = useMemo(() => {
    if (!sheet) return [];
    return sheet.columns.map((col, idx) => {
      const num = idx + 1;
      const tag = col.type === 'text' ? '-T' : col.type === 'date' ? '-D' : '';
      const badges = [
        col.isCalculated ? '• fx' : '',
        col.isLocked ? '• Locked' : '',
        col.role && col.role !== 'CONTINUOUS' ? `• ${col.role}` : '',
      ]
        .filter(Boolean)
        .join(' ');
      const group = `C${num}${tag}${badges ? '  ' + badges : ''}`;

      return {
        id: col.id,
        title: col.name || '',
        group,
        width: col.width || 110,
        themeOverride: col.isLocked
          ? {
              bgCell: '#f8f8f8',
              textDark: '#555555',
            }
          : undefined,
      };
    });
  }, [sheet]);

  // ──────────────────────────────────────────────────────────────
  // Cell content provider — ALL cells are editable Text overlays
  // ──────────────────────────────────────────────────────────────
  const getCellContent = useCallback(
    ([colIdx, rowIdx]: Item): GridCell => {
      // Use getState to fetch the current active sheet without triggering a React re-render
      const state = useWorksheetStore.getState();
      const currentSheet = state.worksheets.find(w => w.id === state.activeSheetId);
      
      const col = currentSheet?.columns[colIdx];
      const row = currentSheet?.rows[rowIdx];
      const locked = Boolean(col?.isLocked);
      const rawVal = col && row ? row[col.id] : undefined;
      const display = rawVal !== undefined && rawVal !== null ? String(rawVal) : '';
      const isNum = display !== '' && !isNaN(Number(display));

      return {
        kind: GridCellKind.Text,
        data: display,
        displayData: display,
        allowOverlay: !locked,
        readonly: locked,
        contentAlign: isNum ? 'right' : 'left',
      };
    },
    []
  );

  // ──────────────────────────────────────────────────────────────
  // Cell edit handler — auto-coerce to number if possible
  // ──────────────────────────────────────────────────────────────
  const onCellEdited = useCallback(
    ([colIdx, rowIdx]: Item, newValue: EditableGridCell) => {
      const col = sheet?.columns[colIdx];
      if (!sheet || !col) return;

      let val: any = null;
      if (newValue.kind === GridCellKind.Text) {
        const s = (newValue.data ?? '').trim();
        if (s === '') {
          val = null;
        } else {
          const n = Number(s);
          val = isNaN(n) ? s : n;
        }
      }
      setCell(sheet.id, rowIdx, col.id, val);
    },
    [sheet, setCell]
  );

  // ──────────────────────────────────────────────────────────────
  // Header click → double-click detection for inline rename
  // ──────────────────────────────────────────────────────────────
  const lastHeaderClick = useRef<{ colIdx: number; time: number }>({ colIdx: -1, time: 0 });

  const onHeaderClicked = useCallback(
    (colIdx: number, event: any) => {
      if (!sheet?.columns[colIdx]) return;
      const col = sheet.columns[colIdx];
      setSelectedColumnId(col.id);

      const now = Date.now();
      const last = lastHeaderClick.current;

      if (last.colIdx === colIdx && now - last.time < 400) {
        const bounds = event.bounds;
        if (bounds && containerRef.current) {
          setHeaderEdit({
            colIdx,
            colId: col.id,
            value: col.name || '',
            rect: {
              x: bounds.x,
              y: bounds.y,
              w: bounds.width,
              h: bounds.height,
            },
          });
        }
        lastHeaderClick.current = { colIdx: -1, time: 0 };
      } else {
        lastHeaderClick.current = { colIdx, time: now };
      }
    },
    [sheet, setSelectedColumnId]
  );

  const commitHeaderEdit = useCallback(() => {
    if (sheet && headerEdit) {
      setColumnName(sheet.id, headerEdit.colId, headerEdit.value.trim());
    }
    setHeaderEdit(null);
  }, [sheet, headerEdit, setColumnName]);

  // ──────────────────────────────────────────────────────────────
  // Right-Click Context Menu Triggers
  // ──────────────────────────────────────────────────────────────
  const calcMenuPos = useCallback((event?: any) => {
    const wrapper = gridWrapperRef.current || containerRef.current;
    if (!wrapper) return { x: 50, y: 50 };
    const rect = wrapper.getBoundingClientRect();
    const MENU_W = 230;
    const MENU_H = 320;

    let rawX: number;
    let rawY: number;

    // Highest priority: precise captured cursor coordinates
    if (lastMousePos.current.clientX > 0 || lastMousePos.current.clientY > 0) {
      rawX = lastMousePos.current.clientX - rect.left;
      rawY = lastMousePos.current.clientY - rect.top;
    } else if (event?.bounds) {
      // In Glide Data Grid, localEventX/Y is cell-relative offset
      const localX = typeof event.localEventX === 'number' ? event.localEventX : 10;
      const localY = typeof event.localEventY === 'number' ? event.localEventY : 10;
      rawX = event.bounds.x + localX;
      rawY = event.bounds.y + localY;
    } else {
      rawX = 50;
      rawY = 50;
    }

    const posX = Math.max(4, Math.min(rawX, rect.width - MENU_W - 8));
    const posY = Math.max(4, Math.min(rawY, rect.height - MENU_H - 8));
    return { x: posX, y: posY };
  }, []);

  const onHeaderContextMenu = useCallback(
    (colIdx: number, event: any) => {
      event.preventDefault?.();
      if (!sheet?.columns[colIdx]) return;
      const col = sheet.columns[colIdx];
      setSelectedColumnId(col.id);

      const pos = calcMenuPos(event);
      setContextMenu({
        type: 'header',
        colIdx,
        x: pos.x,
        y: pos.y,
      });
    },
    [sheet, setSelectedColumnId, calcMenuPos]
  );

  const onCellContextMenu = useCallback(
    ([colIdx, rowIdx]: Item, event: any) => {
      event.preventDefault?.();
      if (!sheet) return;
      const col = sheet.columns[colIdx];
      if (col) {
        setSelectedCell({ rowIdx, colId: col.id });
      }

      const pos = calcMenuPos(event);
      setContextMenu({
        type: 'cell',
        colIdx,
        rowIdx,
        x: pos.x,
        y: pos.y,
      });
    },
    [sheet, setSelectedCell, calcMenuPos]
  );


  // ──────────────────────────────────────────────────────────────
  // Column resize & Row append
  // ──────────────────────────────────────────────────────────────
  const onColumnResize = useCallback(
    (col: GridColumn, newSize: number) => {
      if (!sheet || !col.id) return;
      setColumnWidth(sheet.id, col.id, newSize);
    },
    [sheet, setColumnWidth]
  );

  const onRowAppended = useCallback(() => {
    if (sheet) addRow(sheet.id);
  }, [sheet, addRow]);

  const onPaste = useCallback(
    (target: Item, values: readonly (readonly string[])[]) => {
      if (!sheet) return false;
      pasteMatrix(sheet.id, target[1], target[0], values.map((r) => [...r]));
      return true;
    },
    [sheet, pasteMatrix]
  );

  const onFillPattern = useCallback(
    ({ patternSource: src, fillDestination: dst }: { patternSource: Rectangle; fillDestination: Rectangle }) => {
      if (!sheet) return;
      for (let r = dst.y; r < dst.y + dst.height; r++) {
        const srcRow = sheet.rows[src.y + ((r - dst.y) % src.height)] || {};
        for (let c = dst.x; c < dst.x + dst.width; c++) {
          const colId = sheet.columns[c]?.id;
          const srcColId = sheet.columns[src.x + ((c - dst.x) % src.width)]?.id;
          if (colId && srcColId) setCell(sheet.id, r, colId, srcRow[srcColId]);
        }
      }
    },
    [sheet, setCell]
  );

  const onGridSelectionChange = useCallback(
    (sel: GridSelection) => {
      setGridSelection(sel);
      if (sel.current?.cell) {
        const [c, r] = sel.current.cell;
        setSelectedCell({ rowIdx: r, colId: sheet?.columns[c]?.id || 'c1' });
      }
      const cols = sel.columns.toArray();
      setSelectedColumnId(cols.length > 0 && sheet ? (sheet.columns[cols[0]]?.id ?? null) : null);
      const rows = sel.rows.toArray();
      setSelectedRowIdx(rows.length > 0 ? rows[0] : null);
    },
    [sheet, setSelectedCell, setSelectedColumnId, setSelectedRowIdx]
  );

  if (!sheet) {
    return (
      <div className="flex items-center justify-center h-full text-[#888] text-xs">
        No active worksheet.
      </div>
    );
  }

  const activeContextCol = contextMenu && sheet.columns[contextMenu.colIdx] ? sheet.columns[contextMenu.colIdx] : null;

  return (
    <div
      ref={containerRef}
      className="worksheet-grid-container flex flex-col w-full h-full bg-white overflow-hidden relative select-none"
    >
      {/* ── The Grid Canvas ───────────────────────────────────────── */}
      <div
        ref={gridWrapperRef}
        className="flex-1 min-h-0 relative"
        onContextMenuCapture={(e) => {
          lastMousePos.current = { clientX: e.clientX, clientY: e.clientY };
        }}
        onPointerDownCapture={(e) => {
          lastMousePos.current = { clientX: e.clientX, clientY: e.clientY };
        }}
      >
        <DataEditor
          ref={gridRef}
          columns={gridColumns}
          rows={totalRows}
          getCellContent={getCellContent}
          onCellEdited={onCellEdited}
          gridSelection={gridSelection}
          onGridSelectionChange={onGridSelectionChange}
          rangeSelect="rect"
          columnSelect="multi"
          rowSelect="multi"
          onHeaderClicked={onHeaderClicked}
          onHeaderContextMenu={onHeaderContextMenu}
          onCellContextMenu={onCellContextMenu}
          onColumnResize={onColumnResize}
          onRowAppended={onRowAppended}
          trailingRowOptions={{ hint: 'New row…', sticky: false, tint: true }}
          onPaste={onPaste}
          getCellsForSelection={true}
          fillHandle={true}
          onFillPattern={onFillPattern}
          rowMarkers="number"
          rowHeight={24}
          headerHeight={26}
          groupHeaderHeight={22}
          smoothScrollX
          smoothScrollY
          theme={minitabTheme}
          keybindings={{ search: true }}
          width="100%"
          height="100%"
        />

        {/* ── Inline column-name editor overlay ──────────────────── */}
        {headerEdit && (
          <div
            style={{
              position: 'absolute',
              left: headerEdit.rect.x,
              top: headerEdit.rect.y,
              width: headerEdit.rect.w,
              height: headerEdit.rect.h,
              zIndex: 100,
              boxShadow: '0 2px 8px rgba(0,0,0,0.18)',
            }}
          >
            <input
              ref={headerInputRef}
              type="text"
              value={headerEdit.value}
              onChange={(e) => setHeaderEdit((h) => (h ? { ...h, value: e.target.value } : null))}
              onBlur={commitHeaderEdit}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  commitHeaderEdit();
                } else if (e.key === 'Escape') {
                  setHeaderEdit(null);
                }
              }}
              style={{
                width: '100%',
                height: '100%',
                border: '2px solid #008450',
                outline: 'none',
                padding: '0 4px',
                fontSize: 12,
                fontFamily: '"Segoe UI", system-ui, sans-serif',
                fontWeight: 600,
                color: '#1b1b1b',
                background: '#ffffff',
                boxSizing: 'border-box',
              }}
            />
          </div>
        )}

        {/* ── Right-Click Context Menu Overlay ─────────────────────── */}
        {contextMenu && activeContextCol && (
          <div
            style={{
              position: 'absolute',
              left: contextMenu.x,
              top: contextMenu.y,
              zIndex: 200,
            }}
            className="bg-white border border-[#d2d0ce] shadow-2xl rounded-md py-1 text-xs text-[#201f1e] min-w-[210px] animate-fadeIn select-none"
            onClick={(e) => e.stopPropagation()}
          >
            {contextMenu.type === 'header' ? (
              <>
                <div className="px-3 py-1 text-[11px] font-semibold text-[#605e5c] border-b border-[#edebe9] bg-[#faf9f8]">
                  Column: {activeContextCol.name || `C${contextMenu.colIdx + 1}`}
                </div>

                {/* Rename Column */}
                <button
                  type="button"
                  onClick={() => {
                    setContextMenu(null);
                    setHeaderEdit({
                      colIdx: contextMenu.colIdx,
                      colId: activeContextCol.id,
                      value: activeContextCol.name || '',
                      rect: { x: contextMenu.x, y: 0, w: 120, h: 26 },
                    });
                  }}
                  className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-[#008450] hover:text-white cursor-pointer"
                >
                  <EditRegular className="w-4 h-4" />
                  <span>Rename Column...</span>
                </button>

                <div className="h-px bg-[#edebe9] my-1" />

                {/* Data Type Submenu */}
                <div className="fluent-cascade-item group relative">
                  <div className="px-3 py-1.5 flex items-center justify-between hover:bg-[#008450] hover:text-white cursor-pointer">
                    <div className="flex items-center gap-2">
                      <span>Data Type ({activeContextCol.type?.toUpperCase() || 'NUMERIC'})</span>
                    </div>
                    <ChevronRightRegular className="w-3.5 h-3.5" />
                  </div>
                  <div className="fluent-cascade-flyout absolute left-full top-0 bg-white border border-[#d2d0ce] shadow-xl rounded-md py-1 min-w-[150px] text-xs text-[#201f1e]">
                    {(['numeric', 'text', 'date'] as ColumnDataType[]).map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => {
                          setColumnType(sheet.id, activeContextCol.id, t);
                          setContextMenu(null);
                        }}
                        className="w-full px-3 py-1.5 text-left flex items-center justify-between hover:bg-[#008450] hover:text-white cursor-pointer"
                      >
                        <span className="capitalize">{t}</span>
                        {activeContextCol.type === t && <CheckmarkRegular className="w-3.5 h-3.5" />}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Analytical Role Submenu */}
                <div className="fluent-cascade-item group relative">
                  <div className="px-3 py-1.5 flex items-center justify-between hover:bg-[#008450] hover:text-white cursor-pointer">
                    <div className="flex items-center gap-2">
                      <span>Role ({activeContextCol.role || 'CONTINUOUS'})</span>
                    </div>
                    <ChevronRightRegular className="w-3.5 h-3.5" />
                  </div>
                  <div className="fluent-cascade-flyout absolute left-full top-0 bg-white border border-[#d2d0ce] shadow-xl rounded-md py-1 min-w-[170px] text-xs text-[#201f1e]">
                    {(['CONTINUOUS', 'CATEGORICAL', 'RESPONSE', 'FACTOR', 'BLOCK', 'COVARIATE'] as ColumnAnalyticalRole[]).map((r) => (
                      <button
                        key={r}
                        type="button"
                        onClick={() => {
                          setColumnRole(sheet.id, activeContextCol.id, r);
                          setContextMenu(null);
                        }}
                        className="w-full px-3 py-1.5 text-left flex items-center justify-between hover:bg-[#008450] hover:text-white cursor-pointer"
                      >
                        <span>{r}</span>
                        {activeContextCol.role === r && <CheckmarkRegular className="w-3.5 h-3.5" />}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="h-px bg-[#edebe9] my-1" />

                {/* Quick Sort Ascending / Descending */}
                <button
                  type="button"
                  onClick={() => {
                    sortWorksheet(sheet.id, [{ colId: activeContextCol.id, direction: 'asc' }]);
                    setContextMenu(null);
                  }}
                  className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-[#008450] hover:text-white cursor-pointer"
                >
                  <ArrowSortRegular className="w-4 h-4" />
                  <span>Sort Ascending (A→Z / 1→9)</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    sortWorksheet(sheet.id, [{ colId: activeContextCol.id, direction: 'desc' }]);
                    setContextMenu(null);
                  }}
                  className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-[#008450] hover:text-white cursor-pointer"
                >
                  <ArrowSortRegular className="w-4 h-4" />
                  <span>Sort Descending (Z→A / 9→1)</span>
                </button>

                <div className="h-px bg-[#edebe9] my-1" />

                {/* Insert Column */}
                <button
                  type="button"
                  onClick={() => {
                    addColumn(sheet.id);
                    setContextMenu(null);
                  }}
                  className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-[#008450] hover:text-white cursor-pointer"
                >
                  <AddRegular className="w-4 h-4" />
                  <span>Insert Column</span>
                </button>

                {/* Clear Column */}
                <button
                  type="button"
                  onClick={() => {
                    for (let r = 0; r < sheet.rows.length; r++) {
                      setCell(sheet.id, r, activeContextCol.id, null);
                    }
                    setContextMenu(null);
                  }}
                  className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-[#008450] hover:text-white cursor-pointer text-[#605e5c]"
                >
                  <EraserRegular className="w-4 h-4" />
                  <span>Clear Column Values</span>
                </button>

                {/* Delete Column */}
                <button
                  type="button"
                  onClick={() => {
                    deleteColumn(sheet.id, activeContextCol.id);
                    setContextMenu(null);
                  }}
                  className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-[#c40] hover:text-white cursor-pointer text-[#a80000]"
                >
                  <DeleteRegular className="w-4 h-4" />
                  <span>Delete Column</span>
                </button>
              </>
            ) : (
              /* Cell Context Menu */
              <>
                <div className="px-3 py-1 text-[11px] font-semibold text-[#605e5c] border-b border-[#edebe9] bg-[#faf9f8]">
                  Row {contextMenu.rowIdx !== undefined ? contextMenu.rowIdx + 1 : 1}, Col {activeContextCol.name || `C${contextMenu.colIdx + 1}`}
                </div>

                <button
                  type="button"
                  onClick={() => {
                    if (contextMenu.rowIdx !== undefined) {
                      setCell(sheet.id, contextMenu.rowIdx, activeContextCol.id, null);
                    }
                    setContextMenu(null);
                  }}
                  className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-[#008450] hover:text-white cursor-pointer"
                >
                  <EraserRegular className="w-4 h-4" />
                  <span>Clear Cell</span>
                </button>

                <div className="h-px bg-[#edebe9] my-1" />

                <button
                  type="button"
                  onClick={() => {
                    addRow(sheet.id);
                    setContextMenu(null);
                  }}
                  className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-[#008450] hover:text-white cursor-pointer"
                >
                  <AddRegular className="w-4 h-4" />
                  <span>Insert Row</span>
                </button>

                {contextMenu.rowIdx !== undefined && (
                  <button
                    type="button"
                    onClick={() => {
                      deleteRow(sheet.id, contextMenu.rowIdx!);
                      setContextMenu(null);
                    }}
                    className="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-[#c40] hover:text-white cursor-pointer text-[#a80000]"
                  >
                    <DeleteRegular className="w-4 h-4" />
                    <span>Delete Row {contextMenu.rowIdx + 1}</span>
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* ── Footer Toolbar ────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-3 py-1 bg-[#f3f2f1] border-t border-[#d2d0ce] text-xs text-[#605e5c] shrink-0 gap-2">
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => addRow(sheet.id)}
            className="px-2 py-0.5 border border-[#c8c8c8] rounded text-xs text-[#323130] hover:bg-[#e1dfdd] transition-colors cursor-pointer"
          >
            + Row
          </button>
          <button
            onClick={() => addColumn(sheet.id)}
            className="px-2 py-0.5 border border-[#c8c8c8] rounded text-xs text-[#323130] hover:bg-[#e1dfdd] transition-colors cursor-pointer"
          >
            + Column
          </button>
          {gridSelection.current?.cell && (
            <button
              onClick={() => deleteRow(sheet.id, gridSelection.current!.cell[1])}
              className="px-2 py-0.5 border border-[#c8c8c8] rounded text-xs text-[#c40] hover:bg-[#fde7e9] transition-colors cursor-pointer"
            >
              Delete Row {gridSelection.current.cell[1] + 1}
            </button>
          )}
          {gridSelection.columns.toArray().length > 0 && (
            <button
              onClick={() => {
                const ci = gridSelection.columns.toArray()[0];
                if (sheet.columns[ci]) deleteColumn(sheet.id, sheet.columns[ci].id);
              }}
              className="px-2 py-0.5 border border-[#c8c8c8] rounded text-xs text-[#c40] hover:bg-[#fde7e9] transition-colors cursor-pointer"
            >
              Delete Column
            </button>
          )}
        </div>
        <span className="font-semibold text-[11px]">
          {sheet.rows.length} rows × {sheet.columns.length} cols
          &nbsp;•&nbsp;
          {sheet.rows.filter((r) => Object.values(r).some((v) => v !== null && v !== undefined && v !== '')).length} data rows
        </span>
      </div>


      {/* ── Printable Worksheet Table (Visible exclusively during Print / PDF Export) ── */}
      <div className="hidden print:block printable-worksheet-root w-full bg-white p-2">

        {/* Header Banner */}
        <div className="border-b-2 border-[#008450] pb-2 mb-3">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-bold text-[#111827] tracking-tight">Worksheet: {sheet.name}</h1>
              <p className="text-[11px] text-[#4b5563]">LibRE Sigma Statistical Workspace Worksheet Report</p>
            </div>
            <div className="text-right text-[11px] text-[#4b5563]">
              <p className="font-medium text-[#111827]">{new Date().toLocaleString()}</p>
              <p className="mt-0.5">
                {sheet.rows.length} Total Rows &bull; {sheet.columns.length} Columns
              </p>
            </div>
          </div>
        </div>

        {/* Paginated Worksheet Data Table */}
        <table className="w-full border-collapse border border-[#d1d5db] text-xs">
          <thead>
            <tr className="bg-[#f3f4f6]">
              <th className="border border-[#d1d5db] px-2 py-1 text-center font-bold text-[#374151] w-12 bg-[#e5e7eb]">
                #
              </th>
              {sheet.columns.map((col, idx) => (
                <th key={col.id} className="border border-[#d1d5db] px-2 py-1 text-left font-bold text-[#111827]">
                  <div className="text-[9px] text-[#008450] font-mono">C{idx + 1}-{col.type ? col.type[0].toUpperCase() : 'N'}</div>
                  <div>{col.name}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sheet.rows.map((row, rowIdx) => (
              <tr key={rowIdx} className={rowIdx % 2 === 1 ? 'bg-[#f9fafb]' : 'bg-white'}>
                <td className="border border-[#d1d5db] px-2 py-0.5 text-center font-mono text-[10px] text-[#6b7280] bg-[#f9fafb]">
                  {rowIdx + 1}
                </td>
                {sheet.columns.map((col) => {
                  const val = row[col.id];
                  return (
                    <td
                      key={col.id}
                      className={`border border-[#d1d5db] px-2 py-0.5 text-[11px] ${
                        col.type === 'numeric' ? 'text-right font-mono' : 'text-left'
                      }`}
                    >
                      {val !== null && val !== undefined ? String(val) : ''}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>

        </table>

        {/* Footer Summary */}
        <div className="mt-2 text-[10px] text-[#6b7280] text-right">
          End of Worksheet: {sheet.name} ({sheet.rows.length} rows)
        </div>
      </div>
    </div>
  );
};


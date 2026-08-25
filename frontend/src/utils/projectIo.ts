/**
 * LibRE Sigma Project & Data I/O Engine (.lsg, .ltb, .xlsx, .csv)
 * --------------------------------------------------------
 * - Native LibRE Sigma Project format (.lsg / .ltb): complete state persistence
 *   including multi-sheets, column formulas, analytical roles, locked columns,
 *   DOE design metadata, and interactive session output history (Plotly figures, tables, text).
 * - Excel (.xlsx/.xls) multi-sheet import & export.
 * - Delimited data (.csv/.txt) import & export.
 * - Print / PDF Report generation for statistical results.
 */
import * as XLSX from 'xlsx';
import type { Worksheet, ColumnDef, ColumnDataType, SessionItem, AnalysisResult } from '../types';
import { useWorksheetStore } from '../store/useWorksheetStore';
import { useSessionStore } from '../store/useSessionStore';

export interface LtbProjectFile {
  format: 'libresigma-project' | 'libretab-project' | string;
  version: '1.0.0';
  title: string;
  savedAt: string;
  activeSheetId?: string;
  worksheets: Worksheet[];
  sessionItems: SessionItem[];
}

// ─── Native File Dialog ───────────────────────────────────────────────

/**
 * Opens a native file dialog for selecting LibRE Sigma (.lsg, .ltb), Excel (.xlsx, .xls), or CSV/TXT files.
 */
export const openProjectFileDialog = () => {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.lsg,.libresigma,.ltb,.libretab,.xlsx,.xls,.csv,.txt';
  input.style.display = 'none';

  const cleanup = () => {
    try {
      if (input.parentNode) {
        document.body.removeChild(input);
      }
    } catch {
      /* already removed */
    }
  };

  input.addEventListener('change', async (e: Event) => {
    const target = e.target as HTMLInputElement;
    if (target.files && target.files.length > 0) {
      await handleImportProjectFile(target.files[0]);
    }
    cleanup();
  });

  window.addEventListener(
    'focus',
    () => {
      setTimeout(cleanup, 800);
    },
    { once: true }
  );

  document.body.appendChild(input);
  input.click();
};

// ─── Unified Import Handler ──────────────────────────────────────────

/**
 * General import handler — routes the file to the right parser based on extension.
 * Supports .lsg, .libresigma, .ltb, .libretab, .xlsx, .xls, .csv, .txt.
 */
export const handleImportProjectFile = async (file: File): Promise<boolean> => {
  const ext = file.name.split('.').pop()?.toLowerCase() ?? '';

  try {
    switch (ext) {
      case 'lsg':
      case 'libresigma':
      case 'ltb':
      case 'libretab':
        return await importLtbProjectFile(file);
      case 'xlsx':
      case 'xls':
        return await importExcelFile(file);
      case 'csv':
      case 'txt':
        return await importCsvFile(file);
      default:
        // Try parsing as JSON first, fallback to text
        try {
          const text = await file.text();
          const parsed = JSON.parse(text);
          if (parsed.format === 'libresigma-project' || parsed.format === 'libretab-project' || parsed.worksheets) {
            return await loadLtbData(parsed, file.name);
          }
        } catch {
          // not JSON
        }
        throw new Error(`Unsupported file format ".${ext}". Please select a .lsg, .ltb, .xlsx, .xls, or .csv file.`);
    }
  } catch (err: any) {
    console.error('[ProjectIO] Import failed:', err);
    alert(`Import Error: ${err?.message || String(err)}`);
    return false;
  }
};

// ─── Project Serialization & Ingestion ────────────────────────────────

/**
 * Saves the entire project (all worksheets, formulas, roles, DOE meta, and session reports)
 * to a native LibRE Sigma (.lsg / .ltb) JSON file.
 */
export const saveProjectLtb = async (saveAs: boolean = false): Promise<boolean> => {
  const wsState = useWorksheetStore.getState();
  const sessionState = useSessionStore.getState();

  const activeSheet = wsState.getActiveWorksheet();
  const defaultName = activeSheet?.name ? `${activeSheet.name}` : 'LibRE_Sigma_Project';

  let projectTitle = defaultName;
  if (saveAs) {
    const userInput = prompt('Enter project name:', defaultName);
    if (!userInput) return false; // user cancelled
    projectTitle = userInput.trim();
  }

  try {
    const ltbPayload: LtbProjectFile = {
      format: 'libresigma-project',
      version: '1.0.0',
      title: projectTitle,
      savedAt: new Date().toISOString(),
      activeSheetId: wsState.activeSheetId,
      worksheets: wsState.worksheets.map((ws) => ({
        id: ws.id,
        name: ws.name,
        columns: ws.columns.map((col) => ({
          id: col.id,
          name: col.name,
          type: col.type || 'numeric',
          role: col.role,
          formula: col.formula,
          isCalculated: col.isCalculated,
          isLocked: col.isLocked,
          format: col.format,
          width: col.width || 110,
        })),
        rows: sanitizeRows(ws.rows, ws.columns),
        designMeta: ws.designMeta ? JSON.parse(JSON.stringify(ws.designMeta)) : undefined,
        autoRecalculateFormulas: ws.autoRecalculateFormulas !== false,
      })),
      sessionItems: sessionState.items.map((item) => ({
        id: item.id,
        timestamp: item.timestamp,
        pluginId: item.pluginId,
        pluginName: item.pluginName,
        worksheetName: item.worksheetName,
        params: item.params ? JSON.parse(JSON.stringify(item.params)) : {},
        result: {
          title: item.result?.title || item.pluginName || 'Analysis',
          subtitle: item.result?.subtitle,
          text_output: item.result?.text_output,
          tables: Array.isArray(item.result?.tables) ? JSON.parse(JSON.stringify(item.result.tables)) : [],
          statistics: item.result?.statistics ? JSON.parse(JSON.stringify(item.result.statistics)) : {},
          plotly_figure: item.result?.plotly_figure ? JSON.parse(JSON.stringify(item.result.plotly_figure)) : undefined,
          plotly_figures: Array.isArray(item.result?.plotly_figures) ? JSON.parse(JSON.stringify(item.result.plotly_figures)) : undefined,
        },
      })),
    };

    const jsonString = JSON.stringify(ltbPayload, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json;charset=utf-8' });
    const filename = `${projectTitle.replace(/[\\/:*?"<>|]/g, '_')}.ltb`;
    downloadBlob(blob, filename);
    useWorksheetStore.getState().setIsDirty(false);
    return true;
  } catch (err: any) {
    console.error('[ProjectIO] Save LTB failed:', err);
    alert(`Save Error: ${err?.message || String(err)}`);
    return false;
  }
};

/**
 * Parses and loads a .ltb file stream into the application stores.
 */
async function importLtbProjectFile(file: File): Promise<boolean> {
  const text = await file.text();
  let parsed: any;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error('Invalid .ltb file. File is not a valid JSON document.');
  }
  return loadLtbData(parsed, file.name);
}

/**
 * Loads parsed LTB project data into stores with full schema validation and fallback.
 */
async function loadLtbData(data: any, fileName: string): Promise<boolean> {
  if (!data || typeof data !== 'object') {
    throw new Error('Corrupted .ltb project data.');
  }

  const worksheets = Array.isArray(data.worksheets) ? data.worksheets : [];
  if (worksheets.length === 0) {
    throw new Error('No worksheets found in this .ltb project.');
  }

  // 1. Load worksheets
  const formattedWorksheets: Worksheet[] = worksheets.map((ws: any, idx: number) => {
    const rawCols = Array.isArray(ws.columns) ? ws.columns : [];
    const columns: ColumnDef[] = rawCols.map((c: any, cIdx: number) => ({
      id: String(c.id || `c${cIdx + 1}`),
      name: String(c.name || `C${cIdx + 1}`),
      type: (c.type === 'text' || c.type === 'date' ? c.type : 'numeric') as ColumnDataType,
      role: c.role || undefined,
      formula: c.formula || undefined,
      isCalculated: Boolean(c.isCalculated),
      isLocked: Boolean(c.isLocked),
      format: c.format || undefined,
      width: Number(c.width) || 110,
    }));

    const finalCols = columns.length > 0 ? columns : [{ id: 'c1', name: 'C1', type: 'numeric' as ColumnDataType, width: 110 }];
    const rawRows = Array.isArray(ws.rows) ? ws.rows : [];
    const rows = rawRows.map((r: any) => {
      const normalized: Record<string, any> = {};
      finalCols.forEach((col) => {
        const val = r?.[col.id];
        normalized[col.id] = val === undefined || val === null ? '' : val;
      });
      return normalized;
    });

    return {
      id: String(ws.id || `ws-${Date.now()}-${idx}`),
      name: String(ws.name || `Sheet ${idx + 1}`),
      columns: finalCols,
      rows: rows.length > 0 ? rows : generateEmptyRows(30, finalCols),
      designMeta: ws.designMeta || undefined,
      autoRecalculateFormulas: ws.autoRecalculateFormulas !== false,
    };
  });

  // Replace worksheets in store
  const targetActiveId = data.activeSheetId && formattedWorksheets.some((w) => w.id === data.activeSheetId)
    ? data.activeSheetId
    : formattedWorksheets[0].id;

  useWorksheetStore.setState({
    worksheets: formattedWorksheets,
    activeSheetId: targetActiveId,
    selectedCell: { rowIdx: 0, colId: formattedWorksheets[0].columns[0]?.id || 'c1' },
    selectedRange: null,
    selectedColumnId: null,
    selectedRowIdx: null,
    _undoStack: [],
    _redoStack: [],
    isDirty: false,
  });

  // 2. Restore Session Items
  const rawSessionItems = Array.isArray(data.sessionItems) ? data.sessionItems : [];
  const sessionItems: SessionItem[] = rawSessionItems.map((item: any, sIdx: number) => ({
    id: String(item.id || `out-${Date.now()}-${sIdx}`),
    timestamp: String(item.timestamp || new Date().toLocaleTimeString()),
    pluginId: String(item.pluginId || 'custom_analysis'),
    pluginName: String(item.pluginName || item.result?.title || 'Analysis'),
    worksheetName: String(item.worksheetName || formattedWorksheets[0].name),
    params: item.params || {},
    result: {
      title: String(item.result?.title || item.pluginName || 'Analysis'),
      subtitle: item.result?.subtitle || undefined,
      text_output: item.result?.text_output || undefined,
      tables: Array.isArray(item.result?.tables) ? item.result.tables : [],
      statistics: item.result?.statistics || {},
      plotly_figure: item.result?.plotly_figure || null,
      plotly_figures: Array.isArray(item.result?.plotly_figures) ? item.result.plotly_figures : undefined,
    },
  }));

  useSessionStore.setState({
    items: sessionItems,
    activeItemId: sessionItems.length > 0 ? sessionItems[sessionItems.length - 1].id : null,
  });

  const projectName = data.title || fileName.replace(/\.[^/.]+$/, '');
  document.title = `LibRE Sigma - ${projectName}`;
  return true;
}

// ─── Excel (.xlsx / .xls) Import ──────────────────────────────────────

async function importExcelFile(file: File): Promise<boolean> {
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: 'array', cellDates: true });

  const parsedSheets: Worksheet[] = [];

  for (let sIdx = 0; sIdx < workbook.SheetNames.length; sIdx++) {
    const sheetName = workbook.SheetNames[sIdx];
    const sheet = workbook.Sheets[sheetName];
    if (!sheet) continue;

    const aoa: any[][] = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' });
    if (aoa.length === 0) continue;

    const headerRow = aoa[0];
    const dataRows = aoa.slice(1);

    const columns: ColumnDef[] = headerRow.map((val: any, cIdx: number) => ({
      id: `c${cIdx + 1}`,
      name: String(val ?? `C${cIdx + 1}`).trim() || `C${cIdx + 1}`,
      type: 'numeric' as ColumnDataType,
      width: 110,
    }));

    const rows = dataRows.map((r: any[]) => {
      const rowObj: Record<string, any> = {};
      columns.forEach((col, cIdx) => {
        const raw = r[cIdx];
        if (raw === undefined || raw === null || raw === '') {
          rowObj[col.id] = '';
        } else if (typeof raw === 'number') {
          rowObj[col.id] = raw;
        } else if (typeof raw === 'boolean') {
          rowObj[col.id] = raw ? 1 : 0;
        } else {
          const str = String(raw).trim();
          const num = Number(str);
          if (str !== '' && !isNaN(num) && isFinite(num)) {
            rowObj[col.id] = num;
          } else {
            rowObj[col.id] = str;
            col.type = 'text';
          }
        }
      });
      return rowObj;
    });

    parsedSheets.push({
      id: `ws-import-${Date.now()}-${sIdx}`,
      name: sheetName,
      columns: columns.length > 0 ? columns : [{ id: 'c1', name: 'C1', type: 'numeric', width: 110 }],
      rows: rows.length > 0 ? rows : generateEmptyRows(30, columns),
      autoRecalculateFormulas: true,
    });
  }

  if (parsedSheets.length === 0) {
    throw new Error('No readable sheets found in the Excel workbook.');
  }

  loadWorksheetsIntoStore(parsedSheets);
  return true;
}

// ─── CSV/TSV Import ───────────────────────────────────────────────────

async function importCsvFile(file: File): Promise<boolean> {
  const text = await file.text();
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length === 0) throw new Error('File is empty.');

  const firstLine = lines[0];
  let delimiter = ',';
  if (firstLine.includes('\t')) delimiter = '\t';
  else if (firstLine.includes(';') && !firstLine.includes(',')) delimiter = ';';

  const parseLine = (line: string): string[] => {
    const result: string[] = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') {
        if (inQuotes && i + 1 < line.length && line[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (ch === delimiter && !inQuotes) {
        result.push(current.trim());
        current = '';
      } else {
        current += ch;
      }
    }
    result.push(current.trim());
    return result;
  };

  const headers = parseLine(lines[0]).map((h, i) => h.replace(/^"|"$/g, '') || `C${i + 1}`);

  const columns: ColumnDef[] = headers.map((name, i) => ({
    id: `c${i + 1}`,
    name,
    type: 'numeric' as ColumnDataType,
    width: 110,
  }));

  const rows = lines.slice(1).map((line) => {
    const parts = parseLine(line);
    const rObj: Record<string, any> = {};
    columns.forEach((c, idx) => {
      const raw = (parts[idx] || '').replace(/^"|"$/g, '');
      if (raw === '' || raw === '*' || raw === 'NA' || raw === 'NaN') {
        rObj[c.id] = '';
      } else {
        const num = Number(raw);
        if (!isNaN(num) && isFinite(num)) {
          rObj[c.id] = num;
        } else {
          rObj[c.id] = raw;
          c.type = 'text';
        }
      }
    });
    return rObj;
  });

  const sheetName = file.name.replace(/\.[^/.]+$/, '');
  const newSheet: Worksheet = {
    id: `ws-csv-${Date.now()}`,
    name: sheetName,
    columns,
    rows: rows.length > 0 ? rows : generateEmptyRows(30, columns),
    autoRecalculateFormulas: true,
  };

  loadWorksheetsIntoStore([newSheet]);
  return true;
}

// ─── Excel Export ─────────────────────────────────────────────────────

/**
 * Exports all worksheets to a multi-sheet Excel (.xlsx) workbook.
 */
export const exportProjectXlsx = (title?: string) => {
  const state = useWorksheetStore.getState();
  const activeSheet = state.getActiveWorksheet();
  const fileName = `${(title || activeSheet?.name || 'LibRE_Tab_Data').replace(/[\\/:*?"<>|]/g, '_')}.xlsx`;

  try {
    const workbook = XLSX.utils.book_new();

    state.worksheets.forEach((ws) => {
      const nonEmptyRows = ws.rows.filter((r) =>
        ws.columns.some((c) => {
          const v = r[c.id];
          return v !== undefined && v !== null && v !== '';
        })
      );

      const headers = ws.columns.map((c) => c.name);
      const rowsData = nonEmptyRows.map((r) =>
        ws.columns.map((c) => {
          const v = r[c.id];
          return v === undefined || v === null ? '' : v;
        })
      );

      const aoa = [headers, ...rowsData];
      const sheet = XLSX.utils.aoa_to_sheet(aoa);

      sheet['!cols'] = ws.columns.map((col) => {
        let maxLen = col.name.length;
        nonEmptyRows.slice(0, 200).forEach((r) => {
          const valStr = String(r[col.id] ?? '');
          if (valStr.length > maxLen) maxLen = valStr.length;
        });
        return { wch: Math.min(40, Math.max(8, maxLen + 2)) };
      });

      let safeSheetName = ws.name.replace(/[*?:/\\[\]]/g, '_').substring(0, 31).trim() || 'Sheet';
      let finalName = safeSheetName;
      let dedupCounter = 2;
      while (workbook.SheetNames.includes(finalName)) {
        finalName = `${safeSheetName.substring(0, 28)}_${dedupCounter}`;
        dedupCounter++;
      }

      XLSX.utils.book_append_sheet(workbook, sheet, finalName);
    });

    XLSX.writeFile(workbook, fileName);
  } catch (err: any) {
    console.error('[ProjectIO] Excel export failed:', err);
    alert(`Excel Export Error: ${err?.message || String(err)}`);
  }
};

// ─── Print & PDF Report Generation ────────────────────────────────────

/**
 * Triggers the native high-resolution worksheet report print / PDF generator.
 * Uses a "print portal" approach: injects a full-page standalone HTML document
 * outside the React #root so the entire app chrome is naturally excluded.
 * Exactly matches Minitab's "Print Worksheet" functionality.
 */
export const printSessionReport = () => {
  const activeSheet = useWorksheetStore.getState().getActiveWorksheet();
  if (!activeSheet) return;

  // ── Build table HTML ────────────────────────────────────────────────
  const colHeaders = activeSheet.columns.map((col, idx) => {
    const tag = col.type === 'text' ? '-T' : col.type === 'date' ? '-D' : '';
    return `<th><div style="font-size:8pt;color:#008450;font-family:monospace">C${idx + 1}${tag}</div><div>${col.name || ''}</div></th>`;
  }).join('');

  const rowsHtml = activeSheet.rows.map((row, rIdx) => {
    const cells = activeSheet.columns.map(col => {
      const val = row[col.id];
      const isNum = col.type === 'numeric';
      const display = val !== null && val !== undefined ? String(val) : '';
      return `<td style="text-align:${isNum ? 'right' : 'left'}">${display}</td>`;
    }).join('');
    const bg = rIdx % 2 === 1 ? 'background:#f9fafb' : 'background:#ffffff';
    return `<tr style="${bg}"><td style="text-align:center;font-size:9pt;color:#6b7280;background:#f3f4f6">${rIdx + 1}</td>${cells}</tr>`;
  }).join('');

  const now = new Date().toLocaleString();
  const sheetTitle = activeSheet.name || 'Worksheet';

  const html = `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>LibRE Sigma Worksheet - ${sheetTitle} (${new Date().toLocaleDateString()})</title>
  <style>
    @page { size: letter portrait; margin: 15mm 12mm 15mm 12mm; }
    * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; box-sizing: border-box; }
    body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10pt; background: #fff; color: #111827; margin: 0; padding: 0; }
    .banner { border-bottom: 2.5pt solid #008450; padding-bottom: 8pt; margin-bottom: 10pt; display: flex; justify-content: space-between; align-items: flex-start; }
    .banner-left h1 { font-size: 14pt; font-weight: 700; margin: 0 0 2pt 0; color: #111827; }
    .banner-left p { font-size: 9pt; color: #4b5563; margin: 0; }
    .banner-right { text-align: right; font-size: 9pt; color: #4b5563; }
    .banner-right p { margin: 0; }
    .banner-right .date { font-weight: 600; color: #111827; font-size: 10pt; }
    table { width: 100%; border-collapse: collapse; font-size: 9pt; }
    thead { display: table-header-group; }
    th { background: #f3f4f6; color: #111827; font-weight: 700; font-size: 8pt; padding: 4pt 5pt; border: 0.75pt solid #d1d5db; text-align: left; vertical-align: bottom; }
    td { border: 0.75pt solid #d1d5db; padding: 2.5pt 5pt; font-size: 8.5pt; vertical-align: middle; }
    tr { break-inside: avoid; page-break-inside: avoid; }
    .footer { margin-top: 8pt; font-size: 8pt; color: #6b7280; text-align: right; border-top: 0.75pt solid #e5e7eb; padding-top: 4pt; }
  </style>
</head>
<body>
  <div class="banner">
    <div class="banner-left">
      <h1>Worksheet: ${sheetTitle}</h1>
      <p>LibRE Sigma Statistical Workspace &mdash; Worksheet Report</p>
    </div>
    <div class="banner-right">
      <p class="date">${now}</p>
      <p>${activeSheet.rows.length} Total Rows &bull; ${activeSheet.columns.length} Columns</p>
    </div>
  </div>
  <table>
    <thead>
      <tr>
        <th style="width:32pt;text-align:center">#</th>
        ${colHeaders}
      </tr>
    </thead>
    <tbody>
      ${rowsHtml}
    </tbody>
  </table>
  <div class="footer">End of Worksheet: ${sheetTitle} (${activeSheet.rows.length} rows)</div>
</body>
</html>`;

  // ── Open a dedicated print window via Blob URL (WebView2 compatible) ──
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
  const blobUrl = URL.createObjectURL(blob);

  const printWin = window.open(blobUrl, '_blank', 'width=920,height=750,menubar=no,toolbar=no,location=no');
  if (!printWin) {
    // Fallback: no popup allowed — rare in Tauri but handle gracefully
    URL.revokeObjectURL(blobUrl);
    alert('Could not open print window. Please allow popups for this app.');
    return;
  }

  // Give the browser a frame to finish rendering before triggering print
  printWin.onload = () => {
    printWin.focus();
    printWin.print();
    // Auto-close the print window after the dialog is dismissed
    printWin.onafterprint = () => {
      printWin.close();
      URL.revokeObjectURL(blobUrl);
    };
  };

  // Safety: if onload doesn't fire (edge case), try after 1.5 s
  setTimeout(() => {
    if (!printWin.closed) {
      try {
        printWin.focus();
        printWin.print();
      } catch (_) { /* already triggered */ }
    }
    URL.revokeObjectURL(blobUrl);
  }, 1500);
};










// ─── Helpers ──────────────────────────────────────────────────────────

function loadWorksheetsIntoStore(sheets: any[]) {
  const store = useWorksheetStore.getState();

  for (let i = 0; i < sheets.length; i++) {
    const s = sheets[i];

    const columns: ColumnDef[] = (s.columns || []).map((c: any, cIdx: number) => ({
      id: c.id || `c${cIdx + 1}`,
      name: c.name || `C${cIdx + 1}`,
      type: (c.type === 'text' || c.type === 'date' ? c.type : 'numeric') as ColumnDataType,
      width: c.width || 110,
      role: c.role || undefined,
      formula: c.formula || undefined,
      isCalculated: c.isCalculated || false,
      isLocked: c.isLocked || false,
    }));

    const rows = (s.rows || []).map((r: Record<string, any>) => {
      const normalized: Record<string, any> = {};
      for (const col of columns) {
        const v = r[col.id];
        normalized[col.id] = v === null || v === undefined ? '' : v;
      }
      return normalized;
    });

    const finalRows = rows.length > 0 ? rows : generateEmptyRows(30, columns);
    const finalCols = columns.length > 0 ? columns : [{ id: 'c1', name: 'C1', type: 'numeric' as ColumnDataType, width: 110 }];

    store.createSheet(s.name || `Sheet ${i + 1}`, finalCols, finalRows);
  }
}

function generateEmptyRows(count: number, columns?: ColumnDef[]): Record<string, any>[] {
  return Array.from({ length: count }, () => {
    const row: Record<string, any> = {};
    if (columns) {
      for (const col of columns) {
        row[col.id] = '';
      }
    }
    return row;
  });
}

function sanitizeRows(rows: Record<string, any>[], columns: ColumnDef[]): Record<string, any>[] {
  return rows.map((r) => {
    const clean: Record<string, any> = {};
    for (const col of columns) {
      const v = r[col.id];
      if (v === undefined || v === null || (typeof v === 'number' && isNaN(v))) {
        clean[col.id] = '';
      } else {
        clean[col.id] = v;
      }
    }
    return clean;
  });
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    if (a.parentNode) {
      document.body.removeChild(a);
    }
    URL.revokeObjectURL(url);
  }, 300);
}

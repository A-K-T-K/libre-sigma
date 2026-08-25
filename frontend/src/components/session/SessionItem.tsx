import React, { useState } from 'react';
import {
  Badge,
  Button,
  TabList,
  Tab,
} from '@fluentui/react-components';
import {
  CopyRegular,
  ArrowDownloadRegular,
  DeleteDismissRegular,
  ClockRegular,
  CheckmarkRegular,
  DataBarVerticalRegular,
  GridDotsRegular,
  ChevronDownRegular,
  ChevronRightRegular,
} from '@fluentui/react-icons';
import { SessionItem as SessionItemType } from '../../types';
import { useSessionStore } from '../../store/useSessionStore';
import { PlotlyChart } from './PlotlyChart';

interface SessionItemProps {
  item: SessionItemType;
  isActive?: boolean;
}

export const SessionItem: React.FC<SessionItemProps> = React.memo(({ item, isActive }) => {
  const { removeSessionItem } = useSessionStore();

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [copiedAll, setCopiedAll] = useState(false);
  const [copiedTableIdx, setCopiedTableIdx] = useState<number | null>(null);

  // Helper to format table as TSV (Tab-Separated Values) for perfect Excel pasting
  const formatTableToTSV = (headers: string[], rows: any[][]): string => {
    const headerLine = headers.join('\t');
    const rowLines = rows.map((r) => r.map((c) => (c !== null && c !== undefined ? String(c) : '')).join('\t'));
    return [headerLine, ...rowLines].join('\n');
  };

  // Helper to format table as CSV for download
  const formatTableToCSV = (headers: string[], rows: any[][]): string => {
    const escapeCSV = (val: any) => {
      if (val === null || val === undefined) return '';
      const str = String(val);
      if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };
    const headerLine = headers.map(escapeCSV).join(',');
    const rowLines = rows.map((r) => r.map(escapeCSV).join(','));
    return [headerLine, ...rowLines].join('\n');
  };

  // Copy ALL tables and stats from this analysis formatted for Excel
  const handleCopyAllToExcel = (e: React.MouseEvent) => {
    e.stopPropagation();
    const sections: string[] = [];
    sections.push(`${item.result.title} - ${item.result.subtitle || ''}`);
    sections.push(`Worksheet: ${item.worksheetName} | Date: ${item.timestamp}`);
    sections.push('');

    if (item.result.tables && item.result.tables.length > 0) {
      item.result.tables.forEach((t) => {
        sections.push(`[${t.title}]`);
        sections.push(formatTableToTSV(t.headers, t.rows));
        if (t.notes && t.notes.length > 0) {
          sections.push(t.notes.join('; '));
        }
        sections.push('');
      });
    }

    navigator.clipboard.writeText(sections.join('\n'));
    setCopiedAll(true);
    setTimeout(() => setCopiedAll(false), 2000);
  };

  // Download all tables as CSV/Excel file
  const handleExportAllToExcel = (e: React.MouseEvent) => {
    e.stopPropagation();
    const sections: string[] = [];
    sections.push(`"${item.result.title} - ${item.result.subtitle || ''}"`);
    sections.push(`"Worksheet: ${item.worksheetName} | Date: ${item.timestamp}"`);
    sections.push('');

    if (item.result.tables && item.result.tables.length > 0) {
      item.result.tables.forEach((t) => {
        sections.push(`"${t.title}"`);
        sections.push(formatTableToCSV(t.headers, t.rows));
        if (t.notes && t.notes.length > 0) {
          sections.push(`"${t.notes.join('; ')}"`);
        }
        sections.push('');
      });
    }

    const csvContent = sections.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const safeTitle = (item.result.title || 'analysis').toLowerCase().replace(/[^a-z0-9]/g, '_');
    link.download = `${safeTitle}_results.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // Copy single table to TSV
  const handleCopySingleTable = (tIdx: number, headers: string[], rows: any[][]) => {
    const tsv = formatTableToTSV(headers, rows);
    navigator.clipboard.writeText(tsv);
    setCopiedTableIdx(tIdx);
    setTimeout(() => setCopiedTableIdx(null), 2000);
  };

  // Download single table as CSV
  const handleDownloadSingleTable = (title: string, headers: string[], rows: any[][]) => {
    const csv = formatTableToCSV(headers, rows);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const safeTitle = title.toLowerCase().replace(/[^a-z0-9]/g, '_');
    link.download = `${safeTitle}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div
      id={`session-${item.id}`}
      className={`session-item-card bg-white rounded-lg border transition-all duration-150 mb-4 shadow-sm overflow-hidden ${
        isActive ? 'border-[#008450] ring-2 ring-[#008450]/20' : 'border-[#e0e0e0] hover:border-[#c8c6c4]'
      }`}
    >
      {/* Session Item Header (Click to toggle collapse) */}
      <div
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="flex items-center justify-between px-4 py-2.5 bg-[#f8f9fa] border-b border-[#e0e0e0] cursor-pointer hover:bg-[#f3f2f1] transition-colors select-none"
      >
        <div className="flex items-center space-x-2.5">
          <button
            type="button"
            className="p-0.5 hover:bg-[#e1dfdd] rounded text-[#605e5c] transition-transform cursor-pointer"
            title={isCollapsed ? 'Expand Report' : 'Collapse Report'}
          >
            {isCollapsed ? <ChevronRightRegular className="w-4 h-4 text-[#008450]" /> : <ChevronDownRegular className="w-4 h-4 text-[#008450]" />}
          </button>
          <span className="w-2 h-2 rounded-full bg-[#008450]"></span>
          <h3 className="text-sm font-semibold text-[#201f1e] tracking-tight">
            {item.result.title}
          </h3>
          {item.result.subtitle && (
            <span className="text-xs text-[#605e5c] font-normal hidden sm:inline">
              — {item.result.subtitle}
            </span>
          )}
          <Badge size="small" appearance="tint" color="brand">
            {item.worksheetName}
          </Badge>
          {isCollapsed && item.result.tables && item.result.tables.length > 0 && (
            <span className="text-[11px] text-[#8a8886] italic">
              ({item.result.tables.length} {item.result.tables.length === 1 ? 'table' : 'tables'})
            </span>
          )}
        </div>

        <div className="flex items-center space-x-1.5" onClick={(e) => e.stopPropagation()}>
          <span className="text-[11px] text-[#8a8886] mr-2 flex items-center gap-1 hidden md:flex">
            <ClockRegular className="w-3 h-3" />
            {item.timestamp}
          </span>

          {/* Copy All to Excel Button */}
          <Button
            appearance="secondary"
            size="small"
            icon={copiedAll ? <CheckmarkRegular className="text-green-600" /> : <CopyRegular className="text-[#008450]" />}
            onClick={handleCopyAllToExcel}
            title="Copy all tables formatted for Excel"
          >
            {copiedAll ? 'Copied!' : 'Copy to Excel'}
          </Button>

          {/* Export All to CSV/Excel Button */}
          <Button
            appearance="subtle"
            size="small"
            icon={<ArrowDownloadRegular />}
            onClick={handleExportAllToExcel}
            title="Export all tables as CSV"
          />

          {/* Delete Item Button */}
          <Button
            appearance="subtle"
            size="small"
            icon={<DeleteDismissRegular />}
            onClick={(e) => {
              e.stopPropagation();
              removeSessionItem(item.id);
            }}
            title="Delete this analysis result"
          />
        </div>
      </div>

      {/* Session Item Body */}
      <div className={`p-4 space-y-5 ${isCollapsed ? 'hidden print:block' : 'block'}`}>
        {/* Notes / Narrative Text Output — rendered as clean styled markdown/prose */}
        {item.result.text_output && (
          <TextOutputBlock text={item.result.text_output} />
        )}

        {/* Statistical Tables */}
        {item.result.tables && item.result.tables.length > 0 && (
          <div className="space-y-5">
            {item.result.tables.map((table, tIdx) => (
              <StatisticalTable
                key={tIdx}
                tableIndex={tIdx}
                title={table.title}
                headers={table.headers}
                rows={table.rows}
                notes={table.notes}
                onCopy={() => handleCopySingleTable(tIdx, table.headers, table.rows)}
                onDownload={() => handleDownloadSingleTable(table.title, table.headers, table.rows)}
                isCopied={copiedTableIdx === tIdx}
              />
            ))}
          </div>
        )}

        {/* Plotly Visualizations */}
        {((item.result.plotly_figures && item.result.plotly_figures.length > 0) || item.result.plotly_figure) && (
          <PlotSection figures={item.result.plotly_figures || (item.result.plotly_figure ? [item.result.plotly_figure] : [])} />
        )}
      </div>
    </div>
  );
});

SessionItem.displayName = 'SessionItem';

// ──────────────────────────────────────────────────────────────────────────────
// Helpers for Accurate Column Alignment in Statistical Tables
// ──────────────────────────────────────────────────────────────────────────────

function isNumericValue(val: any): boolean {
  if (val === null || val === undefined) return false;
  if (typeof val === 'number') return true;
  const s = String(val).trim();
  if (s === '' || s === '-' || s === '—' || s === 'N/A' || s === 'Inf' || s === '-Inf' || s === 'None') return false;
  // Match standard numbers, p-values (< 0.001, > 0.999), percentages (95.2%), scientific notation (1.23e-4)
  if (/^[<>]?\s*[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?%?$/.test(s)) return true;
  // Match confidence intervals like (0.1234, 0.5678) or (-Inf, 1.25)
  if (/^\([-+]?(?:\d*\.?\d+|Inf),\s*[-+]?(?:\d*\.?\d+|Inf)\)$/i.test(s)) return true;
  return false;
}

function isCenterValue(val: any): boolean {
  if (val === null || val === undefined) return false;
  const s = String(val).trim();
  if (/^[A-Z](?:\s+[A-Z])*$/.test(s)) return true; // Grouping letters: "A", "B", "A B"
  if (/^(Yes|No|True|False|\*|\+|\-)$/i.test(s)) return true;
  return false;
}

interface StatisticalTableProps {
  title?: string;
  headers: string[];
  rows: any[][];
  notes?: string[];
  tableIndex?: number;
  onCopy?: () => void;
  onDownload?: () => void;
  isCopied?: boolean;
}

export const StatisticalTable: React.FC<StatisticalTableProps> = ({
  title,
  headers,
  rows,
  notes,
  onCopy,
  onDownload,
  isCopied,
}) => {
  // Compute column alignments: guaranteed that <th> and <td> share the EXACT same alignment class
  const colAlignments = React.useMemo(() => {
    return headers.map((header, cIdx) => {
      const trimmedHeader = (header || '').trim();
      if (/^(#|Row|No\.?|Run)$/i.test(trimmedHeader)) {
        return 'text-center';
      }
      if (/^(Grouping|Signif|Status|Code|Flag|Method)$/i.test(trimmedHeader)) {
        return 'text-center';
      }
      if (/^(Source|Term|Parameter|Factor|Specification|Model|Level|Difference\s+of\s+Levels)$/i.test(trimmedHeader)) {
        return 'text-left';
      }

      const nonNullCells = rows
        .map((r) => r[cIdx])
        .filter((v) => v !== null && v !== undefined && String(v).trim() !== '' && String(v).trim() !== '—');

      if (nonNullCells.length === 0) return 'text-left';

      const numCount = nonNullCells.filter(isNumericValue).length;
      const centerCount = nonNullCells.filter(isCenterValue).length;

      if (cIdx === 0 && nonNullCells.some((c) => isNaN(Number(c)) && !isNumericValue(c))) {
        return 'text-left';
      }

      if (numCount / nonNullCells.length >= 0.5) {
        if (cIdx === 0 && !/^(#|N|DF|Order|Lag)$/i.test(trimmedHeader) && isNaN(Number(nonNullCells[0]))) {
          return 'text-left';
        }
        return 'text-right';
      }

      if (centerCount / nonNullCells.length >= 0.5) {
        return 'text-center';
      }

      return 'text-left';
    });
  }, [headers, rows]);

  return (
    <div className="border border-[#d2d0ce] rounded-md overflow-hidden bg-white shadow-xs">
      {/* Table Header Bar with Title & Copy/Download Actions */}
      {title && (
        <div className="flex items-center justify-between px-3.5 py-2 bg-[#f8f9fa] border-b border-[#e1dfdd]">
          <span className="font-semibold text-xs text-[#201f1e] tracking-tight">
            {title}
          </span>
          <div className="flex items-center space-x-1">
            {onCopy && (
              <button
                type="button"
                onClick={onCopy}
                className="flex items-center space-x-1 px-2 py-0.5 text-[11px] text-[#605e5c] hover:text-[#008450] hover:bg-white rounded transition-colors cursor-pointer"
                title="Copy table to clipboard for Excel (TSV)"
              >
                {isCopied ? (
                  <>
                    <CheckmarkRegular className="w-3 h-3 text-green-600" />
                    <span className="text-green-600 font-medium">Copied</span>
                  </>
                ) : (
                  <>
                    <CopyRegular className="w-3 h-3" />
                    <span>Copy Table</span>
                  </>
                )}
              </button>
            )}
            {onDownload && (
              <button
                type="button"
                onClick={onDownload}
                className="p-1 text-[#605e5c] hover:text-[#008450] hover:bg-white rounded transition-colors cursor-pointer"
                title="Download table as CSV"
              >
                <ArrowDownloadRegular className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Structured Table Grid */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-[#f3f2f1] border-b border-[#d2d0ce]">
              {headers.map((h, hIdx) => (
                <th
                  key={hIdx}
                  className={`px-3.5 py-2 font-semibold text-[#323130] text-[11px] uppercase tracking-wider whitespace-nowrap ${colAlignments[hIdx]}`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#edebe9]">
            {rows.map((row, rIdx) => (
              <tr
                key={rIdx}
                className={rIdx % 2 === 0 ? 'bg-white hover:bg-[#f3f9f5] transition-colors' : 'bg-[#fafafa] hover:bg-[#f3f9f5] transition-colors'}
              >
                {row.map((cell, cIdx) => (
                  <td
                    key={cIdx}
                    className={`px-3.5 py-1.5 text-xs text-[#201f1e] whitespace-nowrap tabular-nums ${colAlignments[cIdx]}`}
                  >
                    {cell !== null && cell !== undefined && String(cell).trim() !== '' ? String(cell) : '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Table Notes / Footnotes */}
      {notes && notes.length > 0 && (
        <div className="px-3.5 py-1.5 bg-[#faf9f8] border-t border-[#edebe9] text-[11px] text-[#605e5c] space-y-0.5">
          {notes.map((tn, idx) => (
            <div key={idx} className="italic">
              * {tn}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────────
// Comprehensive Markdown & Table Parser
// ──────────────────────────────────────────────────────────────────────────────

type ParsedBlock =
  | { type: 'table'; headers: string[]; rows: string[][]; title?: string; notes?: string[] }
  | { type: 'equation'; label: string; equation: string }
  | { type: 'metrics'; items: Array<{ key: string; value: string }> }
  | { type: 'hypothesis'; items: Array<{ label: string; statement: string }> }
  | { type: 'heading'; level: number; title: string }
  | { type: 'list'; items: string[] }
  | { type: 'code'; code: string }
  | { type: 'kv'; key: string; value: string }
  | { type: 'prose'; text: string };

function parseMarkdownRow(line: string): string[] {
  let trimmed = line.trim();
  if (trimmed.startsWith('|')) trimmed = trimmed.slice(1);
  if (trimmed.endsWith('|')) trimmed = trimmed.slice(0, -1);
  return trimmed.split('|').map((c) => c.trim());
}

function isMarkdownDivider(line: string): boolean {
  const trimmed = line.trim();
  if (!trimmed.includes('-')) return false;
  // Match standard markdown divider like |:---|:---:|---:| or :---|:--- or --- | ---
  return /^\|?[\s\-:\+\|]+\|?$/.test(trimmed) && trimmed.replace(/[\s\|\:\+]/g, '').length >= 2;
}

function isAsciiGridDivider(line: string): boolean {
  const trimmed = line.trim();
  return /^\+[\-+=\+]+\+$/.test(trimmed);
}

function parseTextOutputBlocks(rawText: string): ParsedBlock[] {
  const rawLines = rawText.split('\n');
  const blocks: ParsedBlock[] = [];

  let i = 0;
  let lastHeading = '';

  while (i < rawLines.length) {
    const line = rawLines[i].trimEnd();
    const trimmed = line.trim();

    if (!trimmed) {
      i++;
      continue;
    }

    // ── 1. Check for Code Block (``` ... ```) ─────────────────────────
    if (trimmed.startsWith('```')) {
      const codeLines: string[] = [];
      i++;
      while (i < rawLines.length && !rawLines[i].trim().startsWith('```')) {
        codeLines.push(rawLines[i]);
        i++;
      }
      i++; // skip closing ```
      blocks.push({ type: 'code', code: codeLines.join('\n') });
      continue;
    }

    // ── 2. Check for Standard Markdown Table ──────────────────────────
    // e.g.
    // | Header 1 | Header 2 |
    // | :--- | :--- |
    // | val 1 | val 2 |
    if ((trimmed.startsWith('|') || trimmed.includes('|')) && i + 1 < rawLines.length) {
      const nextLine = rawLines[i + 1].trim();
      if (isMarkdownDivider(nextLine)) {
        const headers = parseMarkdownRow(trimmed);
        const rows: string[][] = [];
        i += 2; // skip header and divider

        while (i < rawLines.length) {
          const rowLine = rawLines[i].trim();
          if (!rowLine || (!rowLine.startsWith('|') && !rowLine.includes('|'))) {
            break;
          }
          if (isMarkdownDivider(rowLine)) {
            i++;
            continue;
          }
          const cells = parseMarkdownRow(rowLine);
          if (cells.length > 0 && cells.some((c) => c.length > 0)) {
            rows.push(cells);
          }
          i++;
        }

        if (headers.length > 0 && rows.length > 0) {
          blocks.push({ type: 'table', headers, rows, title: lastHeading || undefined });
          lastHeading = '';
          continue;
        }
      }
    }

    // ── 3. Check for ASCII Grid Table (+----+----+) ─────────────────────
    if (isAsciiGridDivider(trimmed) && i + 1 < rawLines.length) {
      const headerLine = rawLines[i + 1].trim();
      if (headerLine.startsWith('|') && i + 2 < rawLines.length && isAsciiGridDivider(rawLines[i + 2].trim())) {
        const headers = parseMarkdownRow(headerLine);
        const rows: string[][] = [];
        i += 3;

        while (i < rawLines.length) {
          const rowLine = rawLines[i].trim();
          if (isAsciiGridDivider(rowLine)) {
            i++;
            continue;
          }
          if (!rowLine.startsWith('|')) break;
          const cells = parseMarkdownRow(rowLine);
          if (cells.length > 0 && cells.some((c) => c.length > 0)) {
            rows.push(cells);
          }
          i++;
        }

        if (headers.length > 0 && rows.length > 0) {
          blocks.push({ type: 'table', headers, rows, title: lastHeading || undefined });
          lastHeading = '';
          continue;
        }
      }
    }

    // ── 4. Check for Space-Separated ASCII Table (Header + Dashed Line) ─
    if (i + 1 < rawLines.length) {
      const nextLine = rawLines[i + 1];
      const nextTrimmed = nextLine.trim();
      const isDashedDivider =
        /^-{2,}(?:\s+-{2,})+$/.test(nextTrimmed) || /^(\s*-{2,}\s*){2,}$/.test(nextTrimmed);

      if (isDashedDivider && trimmed.length > 0 && !trimmed.startsWith('#')) {
        const segments: Array<{ start: number; end: number }> = [];
        const regex = /-+/g;
        let match: RegExpExecArray | null;
        while ((match = regex.exec(nextLine)) !== null) {
          segments.push({ start: match.index, end: match.index + match[0].length });
        }

        if (segments.length >= 2) {
          const headers = segments.map((seg, sIdx) => {
            const nextStart = sIdx + 1 < segments.length ? segments[sIdx + 1].start : line.length + 10;
            return line.slice(seg.start, nextStart).trim();
          });

          const rows: string[][] = [];
          i += 2;
          while (i < rawLines.length) {
            const dataLine = rawLines[i];
            if (!dataLine.trim() || dataLine.trim().startsWith('//')) break;
            if (/^[A-Za-z\s]+:$/.test(dataLine.trim())) break;

            const rowCells = segments.map((seg, sIdx) => {
              const nextStart = sIdx + 1 < segments.length ? segments[sIdx + 1].start : dataLine.length + 10;
              return dataLine.slice(seg.start, nextStart).trim();
            });

            if (rowCells.some((c) => c.length > 0)) {
              rows.push(rowCells);
            }
            i++;
          }

          if (headers.length > 0 && rows.length > 0) {
            blocks.push({ type: 'table', headers, rows, title: lastHeading || undefined });
            lastHeading = '';
            continue;
          }
        }
      }
    }

    // ── 5. Check for Markdown Headings (# Heading, ## Subheading, or standalone **Title**) ─
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const title = headingMatch[2].trim();
      blocks.push({ type: 'heading', level, title });
      lastHeading = title;
      i++;
      continue;
    }

    if (
      ((trimmed.startsWith('**') && trimmed.endsWith('**')) ||
        (trimmed.startsWith('__') && trimmed.endsWith('__'))) &&
      trimmed.length > 4 &&
      !trimmed.slice(2, -2).includes('**') &&
      !trimmed.slice(2, -2).includes(':')
    ) {
      const title = trimmed.slice(2, -2).trim();
      blocks.push({ type: 'heading', level: 2, title });
      lastHeading = title;
      i++;
      continue;
    }

    // ── 6. Check for Equations (Regression Equation, Model Equation, Y =) ─
    if (
      /^(Regression\s+Equation|Fitted\s+Equation|Model\s+Equation|Equation)\s*:/i.test(trimmed) ||
      /^(Y\s*=|Log\(|Logit\(|ln\()/i.test(trimmed)
    ) {
      if (trimmed.includes(':') && trimmed.split(':')[1].trim().length > 0) {
        const parts = trimmed.split(':');
        blocks.push({ type: 'equation', label: parts[0].trim(), equation: parts.slice(1).join(':').trim() });
        i++;
        continue;
      } else if (i + 1 < rawLines.length && rawLines[i + 1].trim().length > 0) {
        blocks.push({ type: 'equation', label: trimmed.replace(':', ''), equation: rawLines[i + 1].trim() });
        i += 2;
        continue;
      }
    }

    // ── 7. Check for Metric Lines (e.g. S = 0.45   R-sq = 94.2%) ─────────
    const metricMatches = [...trimmed.matchAll(/([A-Za-z][A-Za-z0-9\-\(\)\s]{0,15})\s*[:=]\s*([<>]?\s*[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?%?)/g)];
    if (metricMatches.length >= 2) {
      const items = metricMatches.map((m) => ({ key: m[1].trim(), value: m[2].trim() }));
      blocks.push({ type: 'metrics', items });
      i++;
      continue;
    }

    // ── 8. Check for Hypotheses (Null hypothesis, H₀, H₁) ───────────────
    if (/^(H[₀₁0-9]|Null\s+hypothesis|Alternative\s+hypothesis)\s*[:]/i.test(trimmed)) {
      const hypItems: Array<{ label: string; statement: string }> = [];
      while (i < rawLines.length) {
        const cur = rawLines[i].trim();
        if (/^(H[₀₁0-9]|Null\s+hypothesis|Alternative\s+hypothesis)\s*[:]/i.test(cur)) {
          const colonIdx = cur.indexOf(':');
          hypItems.push({ label: cur.slice(0, colonIdx).trim(), statement: cur.slice(colonIdx + 1).trim() });
          i++;
        } else {
          break;
        }
      }
      blocks.push({ type: 'hypothesis', items: hypItems });
      continue;
    }

    // ── 9. Check for Bullet / Numbered Lists (* Item, - Item, 1. Item) ──
    if (/^(\*|\-|\d+\.)\s+/.test(trimmed)) {
      const listItems: string[] = [];
      while (i < rawLines.length) {
        const cur = rawLines[i].trim();
        const m = cur.match(/^(\*|\-|\d+\.)\s+(.+)$/);
        if (m) {
          listItems.push(m[2].trim());
          i++;
        } else {
          break;
        }
      }
      blocks.push({ type: 'list', items: listItems });
      continue;
    }

    // ── 10. Key-Value Pair ──────────────────────────────────────────────
    const kvMatch = trimmed.match(/^([A-Za-z][A-Za-z0-9\s\-\/()%₀₁²³αβσμ]+?)\s*:\s+(.+)$/);
    if (kvMatch && !trimmed.startsWith('//') && !trimmed.startsWith('#')) {
      blocks.push({ type: 'kv', key: kvMatch[1].trim(), value: kvMatch[2].trim() });
      i++;
      continue;
    }

    // ── 11. Section Title Heuristic (e.g. "Factor Information:") ───────
    if (trimmed.endsWith(':') && trimmed.length < 50) {
      blocks.push({ type: 'heading', level: 3, title: trimmed.slice(0, -1) });
      lastHeading = trimmed.slice(0, -1);
      i++;
      continue;
    }

    // ── 12. Plain Prose Text ───────────────────────────────────────────
    blocks.push({ type: 'prose', text: trimmed });
    i++;
  }

  return blocks;
}

function renderFormattedText(text: string): React.ReactNode {
  if (!text) return null;

  // Split by markdown inline patterns: bold (**...** or __...__), code (`...`), italic (*...*)
  const tokens = text.split(/(\*\*[^*]+?\*\*|__[^_]+?__|`[^`]+?`|\*[^*]+?\*)/g);

  return tokens.map((part, index) => {
    if (!part) return null;

    // Bold **...** or __...__
    if (
      (part.startsWith('**') && part.endsWith('**') && part.length >= 4) ||
      (part.startsWith('__') && part.endsWith('__') && part.length >= 4)
    ) {
      const inner = part.slice(2, -2);
      return (
        <strong key={index} className="font-semibold text-[#111827]">
          {renderFormattedText(inner)}
        </strong>
      );
    }

    // Inline Code `...`
    if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      const code = part.slice(1, -1);
      return (
        <code
          key={index}
          className="px-1.5 py-0.5 mx-0.5 bg-[#f3f2f1] text-[#008450] font-mono text-[11px] rounded border border-[#d2d0ce]"
        >
          {code}
        </code>
      );
    }

    // Italic *...*
    if (part.startsWith('*') && part.endsWith('*') && part.length >= 2) {
      const inner = part.slice(1, -1);
      return (
        <em key={index} className="italic text-[#323130]">
          {inner}
        </em>
      );
    }

    return part;
  });
}

const TextOutputBlock: React.FC<{ text: string }> = ({ text }) => {
  const blocks = React.useMemo(() => parseTextOutputBlocks(text), [text]);

  if (!blocks || blocks.length === 0) return null;

  return (
    <div className="space-y-3.5">
      {blocks.map((block, idx) => {
        switch (block.type) {
          case 'table':
            return (
              <StatisticalTable
                key={idx}
                title={block.title}
                headers={block.headers}
                rows={block.rows}
                notes={block.notes}
              />
            );

          case 'equation':
            return (
              <div key={idx} className="bg-[#f8f9fa] border border-[#d2d0ce] border-l-4 border-l-[#008450] rounded-md p-3">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-[#605e5c] block mb-1">
                  {block.label}
                </span>
                <p className="text-sm font-semibold text-[#111827] font-mono">
                  {block.equation}
                </p>
              </div>
            );

          case 'metrics':
            return (
              <div key={idx} className="flex flex-wrap gap-2 pt-1 pb-1">
                {block.items.map((m, mIdx) => (
                  <div
                    key={mIdx}
                    className="inline-flex items-center px-3 py-1 bg-[#f3f2f1] border border-[#d2d0ce] rounded text-xs gap-1.5"
                  >
                    <span className="text-[#605e5c] font-medium">{m.key}:</span>
                    <span className="text-[#111827] font-bold tabular-nums">{m.value}</span>
                  </div>
                ))}
              </div>
            );

          case 'hypothesis':
            return (
              <div key={idx} className="bg-[#faf9f8] border border-[#edebe9] rounded-md p-2.5 space-y-1 text-xs">
                {block.items.map((h, hIdx) => (
                  <div key={hIdx} className="flex items-baseline gap-2">
                    <span className="text-[#0078d4] font-semibold min-w-[140px] shrink-0">
                      {h.label}:
                    </span>
                    <span className="text-[#201f1e] font-medium">{renderFormattedText(h.statement)}</span>
                  </div>
                ))}
              </div>
            );

          case 'heading':
            return (
              <div key={idx} className="pt-2 border-b border-[#e1dfdd] pb-1">
                <h4
                  className={`font-bold tracking-wide ${
                    block.level === 1
                      ? 'text-sm text-[#201f1e]'
                      : block.level === 2
                      ? 'text-xs text-[#008450]'
                      : 'text-xs uppercase text-[#323130]'
                  }`}
                >
                  {renderFormattedText(block.title)}
                </h4>
              </div>
            );

          case 'list':
            return (
              <ul key={idx} className="list-disc list-inside space-y-1.5 text-xs text-[#323130] pl-1">
                {block.items.map((li, lIdx) => (
                  <li key={lIdx} className="leading-relaxed">
                    {renderFormattedText(li)}
                  </li>
                ))}
              </ul>
            );

          case 'code':
            return (
              <pre key={idx} className="bg-[#1e1e1e] text-[#d4d4d4] p-3 rounded text-xs font-mono overflow-x-auto">
                <code>{block.code}</code>
              </pre>
            );

          case 'kv':
            return (
              <div key={idx} className="flex items-baseline gap-2 text-xs">
                <span className="text-[#605e5c] min-w-[120px] shrink-0 font-medium">{renderFormattedText(block.key)}:</span>
                <span className="text-[#201f1e] font-semibold">{renderFormattedText(block.value)}</span>
              </div>
            );

          case 'prose':
            return (
              <p key={idx} className="text-xs text-[#323130] leading-relaxed">
                {renderFormattedText(block.text)}
              </p>
            );

          default:
            return null;
        }
      })}
    </div>
  );
};

interface PlotSectionProps {
  figures: any[];
}

const PlotSection: React.FC<PlotSectionProps> = ({ figures }) => {
  const [selectedTab, setSelectedTab] = useState<string>('0');

  if (!figures || figures.length === 0) return null;

  if (figures.length === 1) {
    return (
      <div className="pt-2">
        <PlotlyChart figure={figures[0]} />
      </div>
    );
  }

  const getTabLabel = (fig: any, idx: number) => {
    const titleText = fig?.layout?.title?.text || '';
    if (titleText.includes('Means')) return 'Main Effects for Means';
    if (titleText.includes('SN') || titleText.includes('Signal')) return 'Main Effects for S/N Ratios';
    return `Plot ${idx + 1}`;
  };

  return (
    <div className="pt-2 space-y-3">
      <TabList
        selectedValue={selectedTab}
        onTabSelect={(_, data) => setSelectedTab(data.value as string)}
        size="small"
      >
        {figures.map((fig, idx) => (
          <Tab key={idx} value={String(idx)} icon={<DataBarVerticalRegular />}>
            {getTabLabel(fig, idx)}
          </Tab>
        ))}
        <Tab value="all" icon={<GridDotsRegular />}>
          View Side-by-Side
        </Tab>
      </TabList>

      <div className="print:hidden">
        {selectedTab === 'all' ? (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {figures.map((fig, idx) => (
              <PlotlyChart key={idx} figure={fig} />
            ))}
          </div>
        ) : (
          <PlotlyChart figure={figures[parseInt(selectedTab, 10) || 0]} />
        )}
      </div>

      <div className="hidden print:flex print:flex-col print:gap-8 w-full">
        {figures.map((fig, idx) => (
          <div key={`print-fig-${idx}`} className="break-inside-avoid page-break-inside-avoid w-full">
            <PlotlyChart figure={fig} />
          </div>
        ))}
      </div>
    </div>
  );
};

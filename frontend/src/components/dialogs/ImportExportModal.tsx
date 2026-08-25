import React, { useState } from 'react';
import {
  Button,
  Field,
  Input,
  Textarea,
  Checkbox,
} from '@fluentui/react-components';
import {
  ArrowUploadRegular,
  DismissRegular,
} from '@fluentui/react-icons';
import { useWorksheetStore } from '../../store/useWorksheetStore';
import { ColumnDef } from '../../types';

interface ImportCsvModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ImportCsvModal: React.FC<ImportCsvModalProps> = ({ isOpen, onClose }) => {
  const [csvText, setCsvText] = useState('');
  const [sheetName, setSheetName] = useState('Imported Data');
  const [hasHeaders, setHasHeaders] = useState(true);
  const { loadDataset } = useWorksheetStore();

  if (!isOpen) return null;

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setSheetName(file.name.replace(/\.[^/.]+$/, ''));
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      setCsvText(text || '');
    };
    reader.readAsText(file);
  };

  const handleImport = () => {
    if (!csvText.trim()) return;

    const lines = csvText.split(/\r\n|\n|\r/).filter((l) => l.trim().length > 0);
    if (lines.length === 0) return;

    let colNames: string[] = [];
    let startLine = 0;

    const parseLine = (line: string) => {
      return line.includes('\t') ? line.split('\t') : line.split(',');
    };

    if (hasHeaders) {
      colNames = parseLine(lines[0]).map((h) => h.trim());
      startLine = 1;
    } else {
      const firstRowCols = parseLine(lines[0]);
      colNames = firstRowCols.map((_, i) => `Col_${i + 1}`);
      startLine = 0;
    }

    const columns: ColumnDef[] = colNames.map((name, i) => ({
      id: `c${i + 1}`,
      name,
      type: 'numeric',
    }));

    const rows: Record<string, any>[] = [];
    for (let i = startLine; i < lines.length; i++) {
      const parts = parseLine(lines[i]);
      const rowObj: Record<string, any> = {};
      columns.forEach((col, cIdx) => {
        const valStr = parts[cIdx]?.trim();
        if (valStr !== undefined && valStr !== '') {
          const num = Number(valStr);
          rowObj[col.id] = !isNaN(num) ? num : valStr;
        }
      });
      rows.push(rowObj);
    }

    loadDataset(sheetName || 'Imported Data', columns, rows);
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-[1px] p-4 select-none animate-in fade-in duration-100"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-full max-w-lg overflow-hidden flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-100">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-[#f8f9fa] border-b border-[#e0e0e0]">
          <div className="flex items-center space-x-2">
            <ArrowUploadRegular className="text-[#0f6cbd]" />
            <h2 className="text-sm font-bold text-[#201f1e]">
              Import CSV / Tab-Delimited Data
            </h2>
          </div>
          <Button
            appearance="subtle"
            size="small"
            icon={<DismissRegular />}
            onClick={onClose}
            style={{ minWidth: '28px', padding: 0 }}
          />
        </div>

        {/* Body */}
        <div className="p-5 space-y-4 max-h-[65vh] overflow-y-auto">
          <Field label={{ children: <span className="text-xs font-semibold text-[#323130]">Worksheet Name</span> }}>
            <Input
              size="small"
              value={sheetName}
              onChange={(_, data) => setSheetName(data.value)}
              className="w-full"
            />
          </Field>

          <Field label={{ children: <span className="text-xs font-semibold text-[#323130]">Select CSV / Text File</span> }}>
            <input
              type="file"
              accept=".csv,.txt,.tsv"
              onChange={handleFileUpload}
              className="w-full text-xs text-[#605e5c] file:mr-2 file:py-1 file:px-3 file:rounded file:border file:border-[#d2d0ce] file:text-xs file:font-semibold file:bg-[#f3f2f1] hover:file:bg-[#edebe9]"
            />
          </Field>

          <Field label={{ children: <span className="text-xs font-semibold text-[#323130]">Or Paste Delimited Data</span> }}>
            <Textarea
              rows={6}
              value={csvText}
              onChange={(_, data) => setCsvText(data.value)}
              placeholder="Paste comma or tab-separated data here..."
              className="w-full text-xs"
            />
          </Field>

          <div>
            <Checkbox
              checked={hasHeaders}
              onChange={(_, data) => setHasHeaders(Boolean(data.checked))}
              label={<span className="text-xs font-medium text-[#323130]">First row contains column headers (variable names)</span>}
            />
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 bg-[#f8f9fa] border-t border-[#e0e0e0] flex justify-end space-x-2">
          <Button appearance="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            appearance="primary"
            onClick={handleImport}
            disabled={!csvText.trim()}
          >
            Import to Worksheet
          </Button>
        </div>
      </div>
    </div>
  );
};

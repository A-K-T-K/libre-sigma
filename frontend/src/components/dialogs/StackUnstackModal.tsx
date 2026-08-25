import React, { useState } from 'react';
import {
  Button,
  Field,
  Input,
  Select,
  Checkbox,
} from '@fluentui/react-components';
import {
  DismissRegular,
  TableRegular,
  PlayRegular,
} from '@fluentui/react-icons';
import { useWorksheetStore } from '../../store/useWorksheetStore';

interface StackUnstackModalProps {
  open: boolean;
  mode: 'stack' | 'unstack';
  onClose: () => void;
}

export const StackUnstackModal: React.FC<StackUnstackModalProps> = ({ open, mode, onClose }) => {
  const { getActiveWorksheet, stackColumns, unstackColumns } = useWorksheetStore();
  const sheet = getActiveWorksheet();

  // Stack State
  const [selectedSourceCols, setSelectedSourceCols] = useState<string[]>([]);
  const [targetDataName, setTargetDataName] = useState<string>('Yield_Stacked');
  const [targetSubscriptName, setTargetSubscriptName] = useState<string>('Machine_Group');

  // Unstack State
  const [unstackRespCol, setUnstackRespCol] = useState<string>('c1');
  const [unstackGroupCol, setUnstackGroupCol] = useState<string>('c3');

  if (!open || !sheet) return null;

  const handleToggleCol = (colId: string) => {
    setSelectedSourceCols((prev) =>
      prev.includes(colId) ? prev.filter((id) => id !== colId) : [...prev, colId]
    );
  };

  const handleExecute = () => {
    if (mode === 'stack') {
      if (selectedSourceCols.length < 2) return;
      stackColumns(sheet.id, selectedSourceCols, targetDataName, targetSubscriptName);
    } else {
      unstackColumns(sheet.id, unstackRespCol, unstackGroupCol);
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center animate-in fade-in duration-150">
      <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-[500px] max-w-[95vw] overflow-hidden">
        {/* Header */}
        <div className="px-5 py-3.5 bg-[#f3f2f1] border-b border-[#e0e0e0] flex items-center justify-between">
          <div className="font-semibold text-sm text-[#201f1e] flex items-center gap-2">
            <TableRegular className="text-[#008450]" />
            <span>{mode === 'stack' ? 'Stack Columns into New Worksheet' : 'Unstack Columns into Separate Columns'}</span>
          </div>
          <Button appearance="subtle" size="small" icon={<DismissRegular />} onClick={onClose} />
        </div>

        {/* Body */}
        <div className="p-5 space-y-4 text-xs text-[#323130]">
          {mode === 'stack' ? (
            <>
              <Field label={{ children: <span className="font-semibold text-[#323130]">Select 2 or more columns to stack</span> }}>
                <div className="max-h-40 overflow-y-auto border border-[#d2d0ce] rounded-md p-2 space-y-1 bg-[#faf9f8]">
                  {sheet.columns.map((col, idx) => (
                    <div
                      key={col.id}
                      onClick={() => handleToggleCol(col.id)}
                      className={`px-2 py-1 rounded cursor-pointer transition-colors flex items-center justify-between ${
                        selectedSourceCols.includes(col.id) ? 'bg-[#e6faf0] text-[#008450] font-semibold' : 'hover:bg-[#f0f0f0]'
                      }`}
                    >
                      <span>{`C${idx + 1}`} {col.name ? `(${col.name})` : ''}</span>
                      <Checkbox checked={selectedSourceCols.includes(col.id)} />
                    </div>
                  ))}
                </div>
              </Field>

              <div className="grid grid-cols-2 gap-3">
                <Field label="Stacked Data Column Name">
                  <Input
                    value={targetDataName}
                    onChange={(_, d) => setTargetDataName(d.value)}
                  />
                </Field>
                <Field label="Subscript / Group Column Name">
                  <Input
                    value={targetSubscriptName}
                    onChange={(_, d) => setTargetSubscriptName(d.value)}
                  />
                </Field>
              </div>
            </>
          ) : (
            <>
              <Field label={{ children: <span className="font-semibold text-[#323130]">Response Column (Data to Unstack)</span> }}>
                <Select
                  value={unstackRespCol}
                  onChange={(_, d) => setUnstackRespCol(d.value)}
                  className="w-full"
                >
                  {sheet.columns.map((c, idx) => (
                    <option key={c.id} value={c.id}>
                      {`C${idx + 1}`} {c.name ? `(${c.name})` : ''}
                    </option>
                  ))}
                </Select>
              </Field>

              <Field label={{ children: <span className="font-semibold text-[#323130]">Grouping Subscript Column</span> }}>
                <Select
                  value={unstackGroupCol}
                  onChange={(_, d) => setUnstackGroupCol(d.value)}
                  className="w-full"
                >
                  {sheet.columns.map((c, idx) => (
                    <option key={c.id} value={c.id}>
                      {`C${idx + 1}`} {c.name ? `(${c.name})` : ''}
                    </option>
                  ))}
                </Select>
              </Field>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 bg-[#f8f9fa] border-t border-[#e0e0e0] flex items-center justify-end gap-2">
          <Button appearance="secondary" size="medium" onClick={onClose}>
            Cancel
          </Button>
          <Button
            appearance="primary"
            size="medium"
            icon={<PlayRegular />}
            onClick={handleExecute}
            disabled={mode === 'stack' && selectedSourceCols.length < 2}
          >
            {mode === 'stack' ? 'Stack into Worksheet' : 'Unstack into Worksheet'}
          </Button>
        </div>
      </div>
    </div>
  );
};

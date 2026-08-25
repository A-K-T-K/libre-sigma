import React, { useState } from 'react';
import {
  Button,
  Field,
  Input,
  Select,
} from '@fluentui/react-components';
import {
  DismissRegular,
  TableRegular,
  AddRegular,
  DeleteRegular,
  PlayRegular,
} from '@fluentui/react-icons';
import { useWorksheetStore } from '../../store/useWorksheetStore';
import { RecodeMapping } from '../../types';

interface RecodeModalProps {
  open: boolean;
  onClose: () => void;
}

export const RecodeModal: React.FC<RecodeModalProps> = ({ open, onClose }) => {
  const { getActiveWorksheet, recodeColumn } = useWorksheetStore();
  const sheet = getActiveWorksheet();

  const [sourceColId, setSourceColId] = useState<string>('c3');
  const [targetColId, setTargetColId] = useState<string>('c5');
  const [mappings, setMappings] = useState<RecodeMapping[]>([
    { fromValue: 'Batch-A', toValue: '1' },
    { fromValue: 'Batch-B', toValue: '2' },
    { fromValue: 'Batch-C', toValue: '3' },
    { fromValue: 'Batch-D', toValue: '4' },
  ]);

  if (!open || !sheet) return null;

  const handleAddRow = () => {
    setMappings([...mappings, { fromValue: '', toValue: '' }]);
  };

  const handleRemoveRow = (idx: number) => {
    setMappings(mappings.filter((_, i) => i !== idx));
  };

  const handleExecute = () => {
    const valid = mappings.filter((m) => m.fromValue.trim() !== '');
    if (valid.length > 0) {
      recodeColumn(sheet.id, sourceColId, targetColId, valid);
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
            <span>Recode Column Values</span>
          </div>
          <Button appearance="subtle" size="small" icon={<DismissRegular />} onClick={onClose} />
        </div>

        {/* Body */}
        <div className="p-5 space-y-4 text-xs text-[#323130]">
          <div className="grid grid-cols-2 gap-3">
            <Field label={{ children: <span className="font-semibold text-[#323130]">Source Column</span> }}>
              <Select
                value={sourceColId}
                onChange={(_, d) => setSourceColId(d.value)}
                className="w-full"
              >
                {sheet.columns.map((c, idx) => (
                  <option key={c.id} value={c.id}>
                    {`C${idx + 1}`} {c.name ? `(${c.name})` : ''}
                  </option>
                ))}
              </Select>
            </Field>

            <Field label={{ children: <span className="font-semibold text-[#323130]">Target Column</span> }}>
              <Select
                value={targetColId}
                onChange={(_, d) => setTargetColId(d.value)}
                className="w-full"
              >
                {sheet.columns.map((c, idx) => (
                  <option key={c.id} value={c.id}>
                    {`C${idx + 1}`} {c.name ? `(${c.name})` : ''}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          <Field label={{ children: <span className="font-semibold text-[#323130]">Value Mapping Table</span> }}>
            <div className="border border-[#d2d0ce] rounded-md p-2 space-y-2 bg-[#faf9f8] max-h-48 overflow-y-auto">
              <div className="grid grid-cols-12 gap-2 text-[11px] font-semibold text-[#605e5c] px-1">
                <span className="col-span-5">Original Value</span>
                <span className="col-span-1 text-center">→</span>
                <span className="col-span-5">Recoded Value</span>
                <span className="col-span-1"></span>
              </div>

              {mappings.map((m, idx) => (
                <div key={idx} className="grid grid-cols-12 gap-2 items-center">
                  <Input
                    className="col-span-5"
                    size="small"
                    value={m.fromValue}
                    onChange={(_, d) => {
                      const next = [...mappings];
                      next[idx].fromValue = d.value;
                      setMappings(next);
                    }}
                    placeholder="From value"
                  />
                  <span className="col-span-1 text-center font-bold text-[#8a8886]">→</span>
                  <Input
                    className="col-span-5"
                    size="small"
                    value={m.toValue}
                    onChange={(_, d) => {
                      const next = [...mappings];
                      next[idx].toValue = d.value;
                      setMappings(next);
                    }}
                    placeholder="To value"
                  />
                  <Button
                    className="col-span-1"
                    appearance="subtle"
                    size="small"
                    icon={<DeleteRegular />}
                    onClick={() => handleRemoveRow(idx)}
                    style={{ minWidth: '24px', padding: 0 }}
                  />
                </div>
              ))}

              <Button
                appearance="subtle"
                size="small"
                icon={<AddRegular />}
                onClick={handleAddRow}
                className="mt-1 text-[#008450]"
              >
                + Add Mapping
              </Button>
            </div>
          </Field>
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
          >
            Recode
          </Button>
        </div>
      </div>
    </div>
  );
};

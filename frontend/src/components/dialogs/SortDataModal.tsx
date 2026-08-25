import React, { useState } from 'react';
import {
  Button,
  Field,
  Select,
  RadioGroup,
  Radio,
} from '@fluentui/react-components';
import {
  DismissRegular,
  ArrowSortRegular,
  PlayRegular,
} from '@fluentui/react-icons';
import { useWorksheetStore } from '../../store/useWorksheetStore';

interface SortDataModalProps {
  open: boolean;
  onClose: () => void;
}

export const SortDataModal: React.FC<SortDataModalProps> = ({ open, onClose }) => {
  const { getActiveWorksheet, sortWorksheet } = useWorksheetStore();
  const sheet = getActiveWorksheet();

  const [col1, setCol1] = useState<string>('c1');
  const [dir1, setDir1] = useState<'asc' | 'desc'>('asc');

  const [col2, setCol2] = useState<string>('none');
  const [dir2, setDir2] = useState<'asc' | 'desc'>('asc');

  if (!open || !sheet) return null;

  const handleSort = () => {
    const sortKeys = [{ colId: col1, direction: dir1 }];
    if (col2 !== 'none' && col2 !== col1) {
      sortKeys.push({ colId: col2, direction: dir2 });
    }

    sortWorksheet(sheet.id, sortKeys, false);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center animate-in fade-in duration-150">
      <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-[460px] max-w-[95vw] overflow-hidden">
        {/* Header */}
        <div className="px-5 py-3.5 bg-[#f3f2f1] border-b border-[#e0e0e0] flex items-center justify-between">
          <div className="font-semibold text-sm text-[#201f1e] flex items-center gap-2">
            <ArrowSortRegular className="text-[#008450]" />
            <span>Sort Worksheet Columns</span>
          </div>
          <Button appearance="subtle" size="small" icon={<DismissRegular />} onClick={onClose} />
        </div>

        {/* Body */}
        <div className="p-5 space-y-4 text-xs text-[#323130]">
          {/* Primary Sort Column */}
          <div className="p-3 bg-[#faf9f8] border border-[#edebe9] rounded-md space-y-2">
            <Field label={{ children: <span className="font-semibold text-[#323130]">Primary Sort By Column</span> }}>
              <Select
                value={col1}
                onChange={(_, d) => setCol1(d.value)}
                className="w-full"
              >
                {sheet.columns.map((c, idx) => (
                  <option key={c.id} value={c.id}>
                    {`C${idx + 1}`} {c.name ? `(${c.name})` : ''}
                  </option>
                ))}
              </Select>
            </Field>
            <RadioGroup
              value={dir1}
              onChange={(_, d) => setDir1(d.value as 'asc' | 'desc')}
              layout="horizontal"
            >
              <Radio value="asc" label="Ascending (A to Z, Low to High)" />
              <Radio value="desc" label="Descending (Z to A, High to Low)" />
            </RadioGroup>
          </div>

          {/* Secondary Sort Column */}
          <div className="p-3 bg-[#faf9f8] border border-[#edebe9] rounded-md space-y-2">
            <Field label={{ children: <span className="font-semibold text-[#323130]">Then Sort By (Optional)</span> }}>
              <Select
                value={col2}
                onChange={(_, d) => setCol2(d.value)}
                className="w-full"
              >
                <option value="none">-- None --</option>
                {sheet.columns.map((c, idx) => (
                  <option key={c.id} value={c.id}>
                    {`C${idx + 1}`} {c.name ? `(${c.name})` : ''}
                  </option>
                ))}
              </Select>
            </Field>
            {col2 !== 'none' && (
              <RadioGroup
                value={dir2}
                onChange={(_, d) => setDir2(d.value as 'asc' | 'desc')}
                layout="horizontal"
              >
                <Radio value="asc" label="Ascending" />
                <Radio value="desc" label="Descending" />
              </RadioGroup>
            )}
          </div>
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
            onClick={handleSort}
          >
            Sort Worksheet
          </Button>
        </div>
      </div>
    </div>
  );
};

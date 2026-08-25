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
  FilterRegular,
  PlayRegular,
} from '@fluentui/react-icons';
import { useWorksheetStore } from '../../store/useWorksheetStore';

interface SubsetWorksheetModalProps {
  open: boolean;
  onClose: () => void;
}

export const SubsetWorksheetModal: React.FC<SubsetWorksheetModalProps> = ({ open, onClose }) => {
  const { getActiveWorksheet, subsetWorksheet } = useWorksheetStore();
  const sheet = getActiveWorksheet();

  const [colId, setColId] = useState<string>('c1');
  const [operator, setOperator] = useState<string>('>');
  const [compareVal, setCompareVal] = useState<string>('1.500');
  const [newSheetName, setNewSheetName] = useState<string>('');

  if (!open || !sheet) return null;

  const handleExecute = () => {
    subsetWorksheet(sheet.id, colId, operator, compareVal, newSheetName.trim() || undefined);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center animate-in fade-in duration-150">
      <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-[460px] max-w-[95vw] overflow-hidden">
        {/* Header */}
        <div className="px-5 py-3.5 bg-[#f3f2f1] border-b border-[#e0e0e0] flex items-center justify-between">
          <div className="font-semibold text-sm text-[#201f1e] flex items-center gap-2">
            <FilterRegular className="text-[#008450]" />
            <span>Subset Worksheet (Filter Rows)</span>
          </div>
          <Button appearance="subtle" size="small" icon={<DismissRegular />} onClick={onClose} />
        </div>

        {/* Body */}
        <div className="p-5 space-y-4 text-xs text-[#323130]">
          <div className="p-3 bg-[#faf9f8] border border-[#edebe9] rounded-md space-y-3">
            <span className="font-semibold text-[#323130]">Include Rows Where:</span>
            <div className="grid grid-cols-12 gap-2 items-center">
              <div className="col-span-5">
                <Select
                  value={colId}
                  onChange={(_, d) => setColId(d.value)}
                  className="w-full"
                >
                  {sheet.columns.map((c, idx) => (
                    <option key={c.id} value={c.id}>
                      {`C${idx + 1}`} {c.name ? `(${c.name})` : ''}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="col-span-3">
                <Select
                  value={operator}
                  onChange={(_, d) => setOperator(d.value)}
                  className="w-full"
                >
                  <option value=">">&gt; (Greater)</option>
                  <option value=">=">&gt;= (Greater/Equal)</option>
                  <option value="<">&lt; (Less)</option>
                  <option value="<=">&lt;= (Less/Equal)</option>
                  <option value="==">== (Equals)</option>
                  <option value="!=">!= (Not Equal)</option>
                </Select>
              </div>

              <div className="col-span-4">
                <Input
                  value={compareVal}
                  onChange={(_, d) => setCompareVal(d.value)}
                  placeholder="Value / text"
                  className="w-full"
                />
              </div>
            </div>
          </div>

          <Field label={{ children: <span className="font-semibold text-[#323130]">New Worksheet Tab Name</span> }}>
            <Input
              value={newSheetName}
              onChange={(_, d) => setNewSheetName(d.value)}
              placeholder={`${sheet.name} (Subset)`}
              className="w-full"
            />
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
            Create Subset
          </Button>
        </div>
      </div>
    </div>
  );
};

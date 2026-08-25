import React, { useState } from 'react';
import {
  Button,
  Field,
  Input,
  RadioGroup,
  Radio,
  Textarea,
  Select,
} from '@fluentui/react-components';
import {
  DismissRegular,
  TableRegular,
  PlayRegular,
} from '@fluentui/react-icons';
import { useWorksheetStore } from '../../store/useWorksheetStore';

interface PatternedDataModalProps {
  open: boolean;
  onClose: () => void;
}

export const PatternedDataModal: React.FC<PatternedDataModalProps> = ({ open, onClose }) => {
  const { getActiveWorksheet, createPatternedData } = useWorksheetStore();
  const sheet = getActiveWorksheet();

  const [dataType, setDataType] = useState<'numeric' | 'text'>('numeric');
  const [targetColId, setTargetColId] = useState<string>('c1');

  // Numeric Sequence Params
  const [fromVal, setFromVal] = useState<number>(1);
  const [toVal, setToVal] = useState<number>(10);
  const [byVal, setByVal] = useState<number>(1);

  // Text List Params
  const [textListStr, setTextListStr] = useState<string>('Operator A\nOperator B\nOperator C');

  // Repetition counts
  const [repeatEach, setRepeatEach] = useState<number>(1);
  const [repeatWhole, setRepeatWhole] = useState<number>(1);

  if (!open || !sheet) return null;

  const handleGenerate = () => {
    const textValues = textListStr
      .split('\n')
      .map((s) => s.trim())
      .filter((s) => s.length > 0);

    createPatternedData(sheet.id, {
      type: dataType,
      targetColId,
      from: Number(fromVal),
      to: Number(toVal),
      by: Number(byVal),
      textValues,
      repeatEachValue: Number(repeatEach),
      repeatWholeSeq: Number(repeatWhole),
    });

    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center animate-in fade-in duration-150">
      <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-[500px] max-w-[95vw] overflow-hidden">
        {/* Header */}
        <div className="px-5 py-3.5 bg-[#f3f2f1] border-b border-[#e0e0e0] flex items-center justify-between">
          <div className="font-semibold text-sm text-[#201f1e] flex items-center gap-2">
            <TableRegular className="text-[#008450]" />
            <span>Create Patterned Data</span>
          </div>
          <Button appearance="subtle" size="small" icon={<DismissRegular />} onClick={onClose} />
        </div>

        {/* Form Body */}
        <div className="p-5 space-y-4 text-xs text-[#323130]">
          {/* Target Column Selector */}
          <Field label={{ children: <span className="font-semibold text-[#323130]">Store Patterned Data In Column</span> }}>
            <Select
              value={targetColId}
              onChange={(_, data) => setTargetColId(data.value)}
              className="w-full"
            >
              {sheet.columns.map((c, idx) => (
                <option key={c.id} value={c.id}>
                  {`C${idx + 1}`} {c.name ? `(${c.name})` : ''}
                </option>
              ))}
            </Select>
          </Field>

          {/* Pattern Type Toggle */}
          <Field label={{ children: <span className="font-semibold text-[#323130]">Pattern Mode</span> }}>
            <RadioGroup
              value={dataType}
              onChange={(_, data) => setDataType(data.value as 'numeric' | 'text')}
              layout="horizontal"
            >
              <Radio value="numeric" label="Simple Numbers Sequence" />
              <Radio value="text" label="Arbitrary Text List" />
            </RadioGroup>
          </Field>

          {/* Mode 1: Numeric Sequence Inputs */}
          {dataType === 'numeric' && (
            <div className="grid grid-cols-3 gap-3 p-3 bg-[#faf9f8] border border-[#edebe9] rounded-md">
              <Field label="From value">
                <Input
                  type="number"
                  value={String(fromVal)}
                  onChange={(_, d) => setFromVal(Number(d.value))}
                />
              </Field>
              <Field label="To value">
                <Input
                  type="number"
                  value={String(toVal)}
                  onChange={(_, d) => setToVal(Number(d.value))}
                />
              </Field>
              <Field label="In steps of">
                <Input
                  type="number"
                  value={String(byVal)}
                  onChange={(_, d) => setByVal(Number(d.value))}
                />
              </Field>
            </div>
          )}

          {/* Mode 2: Text List Input */}
          {dataType === 'text' && (
            <Field label="Text Values (one per line)">
              <Textarea
                rows={4}
                value={textListStr}
                onChange={(_, d) => setTextListStr(d.value)}
                placeholder="Level 1&#10;Level 2&#10;Level 3"
                className="w-full"
              />
            </Field>
          )}

          {/* Repetitions Section */}
          <div className="grid grid-cols-2 gap-3 p-3 bg-[#e6faf0]/60 border border-[#bbf2d6] rounded-md">
            <Field label={{ children: <span className="font-medium text-[#004d2c]">Number of times to repeat each value (K)</span> }}>
              <Input
                type="number"
                min={1}
                value={String(repeatEach)}
                onChange={(_, d) => setRepeatEach(Math.max(1, Number(d.value)))}
              />
            </Field>
            <Field label={{ children: <span className="font-medium text-[#004d2c]">Number of times to repeat the whole sequence (M)</span> }}>
              <Input
                type="number"
                min={1}
                value={String(repeatWhole)}
                onChange={(_, d) => setRepeatWhole(Math.max(1, Number(d.value)))}
              />
            </Field>
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
            onClick={handleGenerate}
          >
            Generate
          </Button>
        </div>
      </div>
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import {
  Button,
  Input,
  Select,
  Tooltip,
  Badge,
} from '@fluentui/react-components';
import {
  MathFormulaRegular,
  CheckmarkCircleRegular,
  ErrorCircleRegular,
  PlayRegular,
  DismissRegular,
  FlashRegular,
} from '@fluentui/react-icons';
import { useWorksheetStore } from '../../store/useWorksheetStore';

export const FormulaBar: React.FC = () => {
  const { getActiveWorksheet, setColumnFormula, clearColumnFormula } = useWorksheetStore();
  const sheet = getActiveWorksheet();

  const [targetColId, setTargetColId] = useState<string>('c1');
  const [formulaText, setFormulaText] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isCalculated, setIsCalculated] = useState<boolean>(false);

  // Sync formula text when target column changes or sheet changes
  useEffect(() => {
    if (sheet) {
      const col = sheet.columns.find((c) => c.id === targetColId) || sheet.columns[0];
      if (col) {
        setTargetColId(col.id);
        setFormulaText(col.formula || '');
        setIsCalculated(Boolean(col.isCalculated && col.formula));
        setErrorMsg(null);
      }
    }
  }, [sheet, targetColId]);

  if (!sheet) return null;

  const handleEvaluate = () => {
    if (!formulaText.trim()) {
      clearColumnFormula(sheet.id, targetColId);
      setErrorMsg(null);
      setIsCalculated(false);
      return;
    }

    const res = setColumnFormula(sheet.id, targetColId, formulaText.trim());
    if (res.success) {
      setErrorMsg(null);
      setIsCalculated(true);
    } else {
      setErrorMsg(res.error || 'Evaluation failed');
    }
  };

  const handleClear = () => {
    setFormulaText('');
    setErrorMsg(null);
    clearColumnFormula(sheet.id, targetColId);
    setIsCalculated(false);
  };

  const handleInsertFunction = (fn: string) => {
    setFormulaText((prev) => {
      const insertStr = `${fn}(C1)`;
      return prev ? `${prev} + ${insertStr}` : insertStr;
    });
  };

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-[#f8f9fa] border-b border-[#d2d0ce] text-xs select-none">
      {/* Formula Icon & Target Column Picker */}
      <div className="flex items-center gap-1.5 shrink-0">
        <div className="flex items-center gap-1 text-[#008450] font-semibold">
          <MathFormulaRegular className="w-4 h-4" />
          <span>Calc:</span>
        </div>

        <select
          value={targetColId}
          onChange={(e) => setTargetColId(e.target.value)}
          className="h-6 px-2 text-xs border border-[#c8c6c4] rounded bg-white font-medium text-[#201f1e] outline-none hover:border-[#008450] focus:border-[#008450]"
        >
          {sheet.columns.map((c) => (
            <option key={c.id} value={c.id}>
              {c.id.toUpperCase()} {c.name ? `(${c.name})` : ''} {c.isCalculated ? '• fx' : ''}
            </option>
          ))}
        </select>

        <span className="text-[#605e5c] font-bold">=</span>
      </div>

      {/* Formula Expression Input Bar */}
      <div className="flex-1 relative flex items-center">
        <input
          type="text"
          value={formulaText}
          onChange={(e) => {
            setFormulaText(e.target.value);
            setErrorMsg(null);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleEvaluate();
            }
          }}
          placeholder="e.g. C1 + C2, LOG(C1), (C1 - MEAN(C1)) / STDEV(C1), ZSCORE(C1)"
          className="w-full h-6 px-2.5 text-xs text-[#201f1e] bg-white border border-[#c8c6c4] rounded outline-none focus:border-[#008450] focus:ring-1 focus:ring-[#008450]"
        />

        {formulaText && (
          <button
            onClick={handleClear}
            className="absolute right-1.5 text-[#8a8886] hover:text-[#d13438] p-0.5"
            title="Clear formula"
          >
            <DismissRegular className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Function Helpers Quick Dropdown */}
      <select
        onChange={(e) => {
          if (e.target.value) {
            handleInsertFunction(e.target.value);
            e.target.value = '';
          }
        }}
        className="h-6 px-1.5 text-[11px] border border-[#c8c6c4] rounded bg-white text-[#605e5c] outline-none"
        defaultValue=""
      >
        <option value="" disabled>+ Function</option>
        <option value="MEAN">MEAN(C1)</option>
        <option value="STDEV">STDEV(C1)</option>
        <option value="ZSCORE">ZSCORE(C1)</option>
        <option value="SUM">SUM(C1)</option>
        <option value="MEDIAN">MEDIAN(C1)</option>
        <option value="LOG">LOG(C1)</option>
        <option value="LN">LN(C1)</option>
        <option value="EXP">EXP(C1)</option>
        <option value="SQRT">SQRT(C1)</option>
        <option value="ABS">ABS(C1)</option>
        <option value="ROUND">ROUND(C1)</option>
        <option value="SIN">SIN(C1)</option>
        <option value="COS">COS(C1)</option>
      </select>

      {/* Action: Evaluate Button */}
      <Button
        appearance="primary"
        size="small"
        icon={<PlayRegular className="w-3.5 h-3.5" />}
        onClick={handleEvaluate}
        style={{ height: '24px', fontSize: '11px', minWidth: '70px', padding: '0 8px' }}
      >
        Calculate
      </Button>

      {/* Status Badge */}
      {isCalculated && !errorMsg && (
        <Badge appearance="tint" color="success" icon={<CheckmarkCircleRegular />} size="small">
          Active Formula
        </Badge>
      )}

      {errorMsg && (
        <Tooltip content={errorMsg} relationship="description">
          <Badge appearance="filled" color="danger" icon={<ErrorCircleRegular />} size="small">
            Error
          </Badge>
        </Tooltip>
      )}
    </div>
  );
};

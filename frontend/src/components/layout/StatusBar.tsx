import React, { useMemo } from 'react';
import { Badge, Spinner } from '@fluentui/react-components';
import {
  GridRegular,
  CheckmarkCircleRegular,
  ErrorCircleRegular,
  CalculatorRegular,
} from '@fluentui/react-icons';
import { useWorksheetStore } from '../../store/useWorksheetStore';
import { usePluginStore } from '../../store/usePluginStore';

export const StatusBar: React.FC = () => {
  const { getActiveWorksheet, selectedCell, selectedColumnId, selectedRowIdx } = useWorksheetStore();
  const { plugins, isLoadingManifest, manifestError, loadManifest } = usePluginStore();

  const sheet = getActiveWorksheet();
  const colIndex = sheet && selectedCell ? sheet.columns.findIndex((c) => c.id === selectedCell.colId) : -1;
  const activeCol = colIndex >= 0 && sheet ? sheet.columns[colIndex] : null;
  const activeCellValue = sheet && selectedCell ? sheet.rows[selectedCell.rowIdx]?.[selectedCell.colId] : undefined;

  // ──────────────────────────────────────────────────────────────
  // Live Selection Aggregate Stats (Count, Sum, Mean, Min, Max, StDev)
  // ──────────────────────────────────────────────────────────────
  const quickStats = useMemo(() => {
    if (!sheet) return null;

    let numbers: number[] = [];
    let countTotal = 0;

    if (selectedColumnId) {
      // Entire Column Selected
      const colRows = sheet.rows.map((r) => r[selectedColumnId]);
      colRows.forEach((v) => {
        if (v !== null && v !== undefined && v !== '') {
          countTotal++;
          const num = Number(v);
          if (!isNaN(num)) numbers.push(num);
        }
      });
    } else if (selectedRowIdx !== null) {
      // Entire Row Selected
      const row = sheet.rows[selectedRowIdx];
      if (row) {
        Object.values(row).forEach((v) => {
          if (v !== null && v !== undefined && v !== '') {
            countTotal++;
            const num = Number(v);
            if (!isNaN(num)) numbers.push(num);
          }
        });
      }
    } else if (selectedCell) {
      // Single Cell Selected
      const val = sheet.rows[selectedCell.rowIdx]?.[selectedCell.colId];
      if (val !== null && val !== undefined && val !== '') {
        countTotal = 1;
        const num = Number(val);
        if (!isNaN(num)) numbers = [num];
      }
    }

    if (numbers.length === 0 && countTotal === 0) return null;

    if (numbers.length === 0) {
      return { count: countTotal, sum: null, mean: null, min: null, max: null, stdev: null };
    }

    const sum = numbers.reduce((a, b) => a + b, 0);
    const mean = sum / numbers.length;
    const min = Math.min(...numbers);
    const max = Math.max(...numbers);

    let stdev = 0;
    if (numbers.length > 1) {
      const sqDiffs = numbers.map((v) => (v - mean) ** 2);
      const variance = sqDiffs.reduce((a, b) => a + b, 0) / (numbers.length - 1);
      stdev = Math.sqrt(variance);
    }

    return {
      count: countTotal,
      numCount: numbers.length,
      sum,
      mean,
      min,
      max,
      stdev: numbers.length > 1 ? stdev : null,
    };
  }, [sheet, selectedColumnId, selectedRowIdx, selectedCell]);

  const formatStat = (val: number | null): string => {
    if (val === null || val === undefined) return '-';
    if (Number.isInteger(val)) return val.toLocaleString();
    return Number(val.toFixed(4)).toString();
  };

  return (
    <div className="flex items-center justify-between px-3 py-1 bg-[#edebe9] border-t border-[#d2d0ce] text-[11px] text-[#484644] select-none shadow-inner status-bar">
      {/* Left: Active Cell Position & Sheet Info */}
      <div className="flex items-center space-x-3">
        <div className="flex items-center gap-1.5">
          <GridRegular className="text-[#605e5c]" />
          {selectedCell && activeCol ? (
            <span>
              Cell: <strong className="text-[#201f1e]">R{selectedCell.rowIdx + 1}C{colIndex + 1}</strong>{' '}
              ({activeCol.name || `C${colIndex + 1}`})
              {activeCellValue !== undefined && (
                <span className="text-[#605e5c] font-normal"> = "{String(activeCellValue)}"</span>
              )}
            </span>
          ) : selectedColumnId && sheet ? (
            <span>
              Column: <strong className="text-[#201f1e]">{sheet.columns.find((c) => c.id === selectedColumnId)?.name || selectedColumnId}</strong>
            </span>
          ) : (
            <span className="font-medium text-[#605e5c]">Ready</span>
          )}
        </div>

        {sheet && <span className="text-[#c8c6c4]">|</span>}

        {sheet && (
          <span className="text-[#323130]">
            Sheet: <strong>{sheet.name}</strong> ({sheet.rows.filter((r) => Object.values(r).some((v) => v !== undefined && v !== '')).length} active rows)
          </span>
        )}
      </div>

      {/* Right: Live Quick Aggregate Statistics + Backend Status */}
      <div className="flex items-center space-x-3">
        {quickStats && (
          <div className="flex items-center gap-2 px-2 py-0.5 bg-white/80 border border-[#d2d0ce] rounded text-[11px] text-[#323130] font-sans">
            <CalculatorRegular className="w-3.5 h-3.5 text-[#008450]" />
            <span>
              <strong>N:</strong> {quickStats.count}
            </span>
            {quickStats.sum !== null && (
              <>
                <span className="text-[#c8c6c4]">|</span>
                <span>
                  <strong>Sum:</strong> {formatStat(quickStats.sum)}
                </span>
                <span className="text-[#c8c6c4]">|</span>
                <span>
                  <strong>Mean:</strong> {formatStat(quickStats.mean)}
                </span>
                <span className="text-[#c8c6c4]">|</span>
                <span>
                  <strong>Min:</strong> {formatStat(quickStats.min)}
                </span>
                <span className="text-[#c8c6c4]">|</span>
                <span>
                  <strong>Max:</strong> {formatStat(quickStats.max)}
                </span>
                {quickStats.stdev !== null && (
                  <>
                    <span className="text-[#c8c6c4]">|</span>
                    <span>
                      <strong>StDev:</strong> {formatStat(quickStats.stdev)}
                    </span>
                  </>
                )}
              </>
            )}
          </div>
        )}

        <div className="flex items-center gap-1.5">
          {manifestError ? (
            <button
              onClick={() => loadManifest()}
              title="Click to reconnect to engine"
              className="cursor-pointer hover:opacity-80 transition-opacity border-0 bg-transparent p-0"
            >
              <Badge appearance="filled" color="danger" icon={<ErrorCircleRegular />}>
                Engine Offline (Click to Retry)
              </Badge>
            </button>
          ) : isLoadingManifest ? (
            <div className="flex items-center gap-1 text-[#0f6cbd] text-[11px]">
              <Spinner size="tiny" />
              <span>Connecting to Engine...</span>
            </div>
          ) : (
            <Badge appearance="tint" color="success" icon={<CheckmarkCircleRegular />}>
              Engine Online ({plugins.length} Plugins)
            </Badge>
          )}
        </div>
      </div>
    </div>
  );
};

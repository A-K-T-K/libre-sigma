import { useMemo } from 'react';
import { useWorksheetStore } from '../store/useWorksheetStore';
import { ColumnDef, ColumnDataType, ColumnAnalyticalRole } from '../types';

export interface WorksheetVariable {
  id: string;
  index: number;
  code: string; // e.g. "C1", "C2-T", "C3-D"
  name: string; // e.g. "Yield", "Machine1"
  label: string; // e.g. "Yield (C1)", "Machine (C2-T)"
  type: ColumnDataType;
  role: ColumnAnalyticalRole;
  isCalculated: boolean;
  isLocked: boolean;
  formula?: string;
  values: any[];
  numericValues: number[];
  uniqueLevels: string[];
}

/**
 * Reactive hook supplying available worksheet columns, types, labels, and data arrays
 * to seamlessly populate variable selectors across all statistical analysis modals.
 */
export const useActiveWorksheetVariables = (): {
  sheetName: string;
  variables: WorksheetVariable[];
  numericVariables: WorksheetVariable[];
  categoricalVariables: WorksheetVariable[];
  getVariableByCodeOrName: (identifier: string) => WorksheetVariable | undefined;
} => {
  const { getActiveWorksheet } = useWorksheetStore();
  const sheet = getActiveWorksheet();

  return useMemo(() => {
    if (!sheet) {
      return {
        sheetName: '',
        variables: [],
        numericVariables: [],
        categoricalVariables: [],
        getVariableByCodeOrName: () => undefined,
      };
    }

    const variables: WorksheetVariable[] = sheet.columns.map((col, idx) => {
      const baseCode = `C${idx + 1}`;
      const code = col.type === 'text' ? `${baseCode}-T` : col.type === 'date' ? `${baseCode}-D` : baseCode;
      const label = col.name ? `${col.name} (${code})` : code;

      const rawValues = sheet.rows.map((r) => r[col.id]);
      const validValues = rawValues.filter((v) => v !== undefined && v !== null && v !== '');

      const numericValues: number[] = [];
      const levelsSet = new Set<string>();

      validValues.forEach((v) => {
        const num = Number(v);
        if (!isNaN(num)) {
          numericValues.push(num);
        }
        levelsSet.add(String(v));
      });

      return {
        id: col.id,
        index: idx + 1,
        code,
        name: col.name,
        label,
        type: col.type,
        role: col.role || 'CONTINUOUS',
        isCalculated: Boolean(col.isCalculated),
        isLocked: Boolean(col.isLocked),
        formula: col.formula,
        values: validValues,
        numericValues,
        uniqueLevels: Array.from(levelsSet),
      };
    });

    const numericVariables = variables.filter((v) => v.type === 'numeric');
    const categoricalVariables = variables.filter((v) => v.type === 'text');

    const getVariableByCodeOrName = (identifier: string): WorksheetVariable | undefined => {
      if (!identifier) return undefined;
      const clean = identifier.trim().toLowerCase();
      return variables.find(
        (v) =>
          v.id.toLowerCase() === clean ||
          v.code.toLowerCase() === clean ||
          v.name.toLowerCase() === clean ||
          v.label.toLowerCase() === clean
      );
    };

    return {
      sheetName: sheet.name,
      variables,
      numericVariables,
      categoricalVariables,
      getVariableByCodeOrName,
    };
  }, [sheet]);
};

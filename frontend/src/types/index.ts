export interface TableResult {
  title: string;
  headers: string[];
  rows: (string | number | null)[][];
  notes?: string[];
}

export interface PlotlyFigureSpec {
  data: any[];
  layout: Record<string, any>;
  config?: Record<string, any>;
}

export interface AnalysisResult {
  title: string;
  subtitle?: string;
  text_output?: string;
  tables: TableResult[];
  statistics: Record<string, any>;
  plotly_figure?: PlotlyFigureSpec | null;
  plotly_figures?: PlotlyFigureSpec[];
  action_type?: string;
  worksheet_data?: {
    name?: string;
    columns: ColumnDef[];
    rows: Record<string, any>[];
  };
}

export interface PluginManifestItem {
  id: string;
  name: string;
  menu_path: string[];
  description: string;
  param_schema: Record<string, any>;
}

export interface MenuNode {
  id: string;
  label: string;
  pluginId?: string;
  children?: MenuNode[];
  divider?: boolean;
  shortcut?: string;
  disabled?: boolean;
}

export interface SessionItem {
  id: string;
  timestamp: string;
  pluginId: string;
  pluginName: string;
  result: AnalysisResult;
  params: Record<string, any>;
  worksheetName: string;
}

export type ColumnDataType = 'numeric' | 'text' | 'date';
export type ColumnAnalyticalRole = 'CONTINUOUS' | 'CATEGORICAL' | 'BLOCK' | 'RESPONSE' | 'COVARIATE' | 'SUBGROUP' | 'FREQUENCY' | 'FITS' | 'RESIDUALS';

export interface ColumnFormat {
  decimals?: number;
  dateFormat?: string;
}

export interface ColumnDef {
  id: string; // Physical ID e.g. 'c1', 'c2', 'c3'
  name: string; // User-editable variable name e.g. 'Yield', 'Machine1'
  type: ColumnDataType; // Inferred or explicit type
  role?: ColumnAnalyticalRole; // Analytical designation (Factor, Response, Block, Covariate)
  formula?: string; // Optional calculated formula e.g. "C1 + C2" or "LOG(C1)"
  isCalculated?: boolean; // True if populated via formula
  isLocked?: boolean; // True if immutable system generated (e.g. FITS1, RESI1)
  format?: ColumnFormat; // Precision formatting
  width?: number; // Display column width in px
  data?: Array<number | string | null>; // Columnar array backing storage
}

export interface DoeDesignMeta {
  type: 'factorial' | 'rsm' | 'mixture' | 'taguchi' | string;
  factorNames: string[];
  responseColName?: string;
  runs?: number;
  factors?: number;
  resolution?: string;
  alpha?: number;
  total?: number;
  arrayName?: string;
}

export type TaguchiDesignMeta = DoeDesignMeta;

export interface Worksheet {
  id: string;
  name: string;
  columns: ColumnDef[];
  rows: Record<string, any>[];
  designMeta?: DoeDesignMeta;
  autoRecalculateFormulas?: boolean;
}

export interface SampleDatasetMeta {
  id: string;
  name: string;
  description: string;
  row_count: number;
  column_count: number;
  preview_columns: string[];
}

export interface PatternedDataConfig {
  type: 'numeric' | 'text';
  targetColId: string;
  // Numeric Sequence
  from?: number;
  to?: number;
  by?: number;
  // Text List
  textValues?: string[];
  // Repetitions
  repeatWholeSeq: number; // M times
  repeatEachValue: number; // K times
}

export interface SortKeyConfig {
  colId: string;
  direction: 'asc' | 'desc';
}

export interface RecodeMapping {
  fromValue: string;
  toValue: string;
}

export interface RecodeRangeRule {
  minVal?: number;
  maxVal?: number;
  toValue: any;
}

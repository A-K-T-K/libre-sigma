import { create } from 'zustand';
import { computeAnalysis, fetchManifest } from '../services/api';
import { MenuNode, PluginManifestItem } from '../types';
import { useSessionStore } from './useSessionStore';
import { useWorksheetStore } from './useWorksheetStore';

interface PluginState {
  plugins: PluginManifestItem[];
  isLoadingManifest: boolean;
  manifestError: string | null;
  activePluginId: string | null;
  isComputing: boolean;
  computeError: string | null;

  // Actions
  loadManifest: () => Promise<void>;
  openDialog: (pluginId: string) => void;
  closeDialog: () => void;
  runCompute: (pluginId: string, params: Record<string, any>) => Promise<boolean>;
  getPlugin: (pluginId: string) => PluginManifestItem | undefined;
  getMenuTree: () => MenuNode[];
}

export const usePluginStore = create<PluginState>((set, get) => ({
  plugins: [],
  isLoadingManifest: false,
  manifestError: null,
  activePluginId: null,
  isComputing: false,
  computeError: null,

  loadManifest: async (retryCount = 25, retryInterval = 800) => {
    set({ isLoadingManifest: true, manifestError: null });
    for (let attempt = 1; attempt <= retryCount; attempt++) {
      try {
        const manifest = await fetchManifest();
        set({ plugins: manifest, isLoadingManifest: false, manifestError: null });
        return;
      } catch (err: any) {
        if (attempt < retryCount) {
          await new Promise((r) => setTimeout(r, retryInterval));
        } else {
          set({
            manifestError: err.message || 'Failed to connect to OpenMinitab Engine',
            isLoadingManifest: false,
          });
        }
      }
    }
  },

  openDialog: (pluginId: string) => {
    set({ activePluginId: pluginId, computeError: null });
  },

  closeDialog: () => {
    set({ activePluginId: null, computeError: null });
  },

  getPlugin: (pluginId: string) => {
    return get().plugins.find((p) => p.id === pluginId);
  },

  runCompute: async (pluginId: string, params: Record<string, any>) => {
    const plugin = get().plugins.find((p) => p.id === pluginId);
    if (!plugin) {
      set({ computeError: `Plugin ${pluginId} not found.` });
      return false;
    }

    const activeSheet = useWorksheetStore.getState().getActiveWorksheet();
    const isGenerator = pluginId.includes('create') || pluginId.includes('generate');

    // Filter out rows that are completely empty
    const cleanRows = activeSheet
      ? activeSheet.rows.filter((r) => Object.values(r).some((v) => v !== undefined && v !== ''))
      : [];

    if (!isGenerator && cleanRows.length === 0) {
      set({ computeError: 'Active worksheet has no data. Enter data or load a sample dataset first.' });
      return false;
    }

    set({ isComputing: true, computeError: null });

    try {
      const result = await computeAnalysis(
        pluginId,
        cleanRows,
        activeSheet?.columns || [],
        params
      );
      
      // If plugin generates or overwrites worksheet data, load it into worksheet store
      if (result.action_type === 'worksheet_overwrite' && result.worksheet_data) {
        let designMeta = undefined;
        if (result.statistics?.factor_names || result.statistics?.component_names) {
          const fNames = result.statistics.factor_names || result.statistics.component_names;
          let dType = 'doe';
          if (pluginId.includes('factorial')) dType = 'factorial';
          else if (pluginId.includes('rsm')) dType = 'rsm';
          else if (pluginId.includes('mixture')) dType = 'mixture';
          else if (pluginId.includes('taguchi')) dType = 'taguchi';

          designMeta = {
            type: dType,
            factorNames: fNames,
            responseColName: 'Response_1',
            runs: result.statistics.runs,
            factors: result.statistics.factors || result.statistics.components,
            resolution: result.statistics.resolution,
            alpha: result.statistics.alpha,
            total: result.statistics.mixture_total,
            arrayName: result.statistics.array,
          };
        }

        useWorksheetStore.getState().loadDataset(
          result.worksheet_data.name || 'DOE Design',
          result.worksheet_data.columns,
          result.worksheet_data.rows,
          designMeta
        );
      } else if (result.action_type === 'worksheet_append_columns' && result.worksheet_data && activeSheet) {
        useWorksheetStore.getState().appendColumns(
          activeSheet.id,
          result.worksheet_data.columns || [],
          result.worksheet_data.rows || []
        );
      }

      // Push result into session output pane
      useSessionStore.getState().addSessionItem(
        plugin.id,
        plugin.name,
        result,
        params,
        result.worksheet_data?.name || activeSheet?.name || 'Worksheet'
      );

      set({ isComputing: false, activePluginId: null });
      return true;
    } catch (err: any) {
      set({ isComputing: false, computeError: err.message || 'Analysis failed.' });
      return false;
    }
  },

  getMenuTree: () => {
    const { plugins } = get();
    // Static base menu roots
    const rootNodes: MenuNode[] = [
      {
        id: 'file',
        label: 'File',
        children: [
          { id: 'file-new', label: 'New Project', shortcut: 'Ctrl+N' },
          { id: 'file-new-sheet', label: 'New Worksheet' },
          { id: 'file-open-project', label: 'Open Project / Data (.ltb, .xlsx, .csv)...', shortcut: 'Ctrl+O' },
          { id: 'file-save-project', label: 'Save Project (.ltb)...', shortcut: 'Ctrl+S' },
          { id: 'file-save-as-project', label: 'Save Project As (.ltb)...', shortcut: 'Ctrl+Shift+S' },
          { id: 'file-divider-1', label: '', divider: true },
          { id: 'file-import-xlsx', label: 'Import Excel Workbook (.xlsx, .xls)...', shortcut: 'Ctrl+I' },
          { id: 'file-export-xlsx', label: 'Export Excel Workbook (.xlsx)...', shortcut: 'Ctrl+E' },
          { id: 'file-import-csv', label: 'Import CSV / Text Data...' },
          { id: 'file-export-csv', label: 'Export Current Sheet as CSV' },
          { id: 'file-divider-2', label: '', divider: true },
          { id: 'file-print-report', label: 'Print / Export PDF Report...', shortcut: 'Ctrl+P' },
          { id: 'file-export-session', label: 'Export Session Transcript (.txt)' },
          { id: 'file-divider-3', label: '', divider: true },
          { id: 'file-sample', label: 'Open Sample Dataset...' },
        ],



      },
      {
        id: 'edit',
        label: 'Edit',
        children: [
          { id: 'edit-undo', label: 'Undo', shortcut: 'Ctrl+Z' },
          { id: 'edit-redo', label: 'Redo', shortcut: 'Ctrl+Y' },
          { id: 'edit-divider-1', label: '', divider: true },
          { id: 'edit-clear-cells', label: 'Clear Cells' },
          { id: 'edit-delete-cells', label: 'Delete Cells' },
          { id: 'edit-copy-cells', label: 'Copy Cells', shortcut: 'Ctrl+C' },
          { id: 'edit-cut-cells', label: 'Cut Cells', shortcut: 'Ctrl+X' },
          { id: 'edit-paste-cells', label: 'Paste Cells', shortcut: 'Ctrl+V' },
        ],
      },
      {
        id: 'data',
        label: 'Data',
        children: [
          { id: 'data-patterned', label: 'Create Patterned Data...' },
          { id: 'data-sort', label: 'Sort Columns...' },
          { id: 'data-divider-1', label: '', divider: true },
          { id: 'data-stack', label: 'Stack Columns...' },
          { id: 'data-unstack', label: 'Unstack Columns...' },
          { id: 'data-divider-2', label: '', divider: true },
          { id: 'data-recode', label: 'Recode Data...' },
          { id: 'data-subset', label: 'Subset Worksheet...' },
        ],
      },
      {
        id: 'calc',
        label: 'Calc',
        children: [
          { id: 'calc-random', label: 'Random Normal Data Generator...' },
          { id: 'calc-stats-row', label: 'Row Statistics' },
        ],
      },
      {
        id: 'stat',
        label: 'Stat',
        children: [],
      },
      {
        id: 'graph',
        label: 'Graph',
        children: [
          { id: 'graph-hist', label: 'Histogram (via Descriptives)', pluginId: 'display_descriptives' },
          { id: 'graph-box', label: 'Boxplot (via 2-Sample t)', pluginId: 'two_sample_t' },
          { id: 'graph-interval', label: 'Interval Plot (via ANOVA)', pluginId: 'one_way_anova' },
          { id: 'graph-scatter', label: 'Fitted Line Plot (via Correlation)', pluginId: 'correlation' },
        ],
      },
      {
        id: 'help',
        label: 'Help',
        children: [
          { id: 'help-about', label: 'About LibRE Tab...' },
          { id: 'help-docs', label: 'Plugin Architecture Guide' },
        ],

      },
    ];

    // Build recursive paths from plugins
    plugins.forEach((plugin) => {
      const path = plugin.menu_path; // e.g. ["Stat", "Basic Statistics", "Display Descriptive Statistics"]
      if (!path || path.length === 0) return;

      const topLevelLabel = path[0];
      let topNode = rootNodes.find((n) => n.label.toLowerCase() === topLevelLabel.toLowerCase());
      if (!topNode) {
        topNode = {
          id: topLevelLabel.toLowerCase(),
          label: topLevelLabel,
          children: [],
        };
        rootNodes.push(topNode);
      }

      let currentLevel = topNode.children || (topNode.children = []);

      for (let i = 1; i < path.length - 1; i++) {
        const seg = path[i];
        let subNode = currentLevel.find((n) => n.label.toLowerCase() === seg.toLowerCase());
        if (!subNode) {
          const pathId = path.slice(0, i + 1).join('-').toLowerCase().replace(/\s+/g, '-');
          subNode = {
            id: `menu-${pathId}`,
            label: seg,
            children: [],
          };
          currentLevel.push(subNode);
        }
        currentLevel = subNode.children || (subNode.children = []);
      }

      const leafLabel = path[path.length - 1] || plugin.name;
      // Check if leaf already exists
      const existing = currentLevel.find((n) => n.pluginId === plugin.id);
      if (!existing) {
        currentLevel.push({
          id: `plugin-${plugin.id}`,
          label: leafLabel,
          pluginId: plugin.id,
        });
      }
    });

    return rootNodes;
  },
}));

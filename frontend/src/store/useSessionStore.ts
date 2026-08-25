import { create } from 'zustand';
import { AnalysisResult, SessionItem } from '../types';
import { useWorksheetStore } from './useWorksheetStore';

interface SessionState {
  items: SessionItem[];
  activeItemId: string | null;
  
  // Actions
  addSessionItem: (
    pluginId: string,
    pluginName: string,
    result: AnalysisResult,
    params: Record<string, any>,
    worksheetName: string
  ) => string;
  removeSessionItem: (id: string) => void;
  clearSession: () => void;
  setActiveItem: (id: string | null) => void;
  exportSessionText: () => string;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  items: [],
  activeItemId: null,

  addSessionItem: (pluginId, pluginName, result, params, worksheetName) => {
    const id = `out-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    const now = new Date();
    const timestamp = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    const newItem: SessionItem = {
      id,
      timestamp,
      pluginId,
      pluginName,
      result,
      params,
      worksheetName,
    };

    set((state) => ({
      items: [...state.items, newItem],
      activeItemId: id,
    }));

    useWorksheetStore.getState().setIsDirty(true);
    return id;
  },

  removeSessionItem: (id) => {
    set((state) => ({
      items: state.items.filter((item) => item.id !== id),
      activeItemId: state.activeItemId === id ? (state.items[0]?.id || null) : state.activeItemId,
    }));
    useWorksheetStore.getState().setIsDirty(true);
  },

  clearSession: () => {
    set({ items: [], activeItemId: null });
  },

  setActiveItem: (id) => {
    set({ activeItemId: id });
  },

  exportSessionText: () => {
    const { items } = get();
    if (items.length === 0) return 'OpenMinitab Session - No outputs recorded.';

    const lines = [
      '========================================================================',
      '                     OpenMinitab Session Transcript                     ',
      `                     Generated: ${new Date().toLocaleString()}         `,
      '========================================================================',
      '',
    ];

    items.forEach((item, idx) => {
      lines.push(`\n[${idx + 1}] ${item.result.title.toUpperCase()}`);
      lines.push(`Timestamp: ${item.timestamp} | Worksheet: ${item.worksheetName}`);
      if (item.result.subtitle) {
        lines.push(`Subtitle: ${item.result.subtitle}`);
      }
      lines.push('------------------------------------------------------------------------');
      if (item.result.text_output) {
        lines.push(item.result.text_output);
      }
      lines.push('');
    });

    return lines.join('\n');
  },
}));

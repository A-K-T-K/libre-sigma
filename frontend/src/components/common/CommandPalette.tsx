import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  SearchRegular,
  DismissRegular,
  DataBarVerticalRegular,
  TableRegular,
  DocumentArrowUpRegular,
  DocumentArrowDownRegular,
  DocumentAddRegular,
  SaveRegular,
  PrintRegular,
  FolderOpenRegular,
  SparkleRegular,
  BranchForkRegular,
  ArrowSortRegular,
  LayerDiagonalRegular,
  TextGrammarErrorRegular,
  FilterRegular,
  InfoRegular,
} from '@fluentui/react-icons';
import { usePluginStore } from '../../store/usePluginStore';
import { useWorksheetStore } from '../../store/useWorksheetStore';
import {
  saveProjectLtb,
  openProjectFileDialog,
  exportProjectXlsx,
  printSessionReport,
} from '../../utils/projectIo';
import { guardUnsavedChanges } from '../../hooks/useUnsavedGuard';


interface CommandItem {
  id: string;
  title: string;
  category: string;
  description?: string;
  shortcut?: string;
  icon: React.ReactNode;
  action: () => void;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenFactorialModal?: () => void;
  onOpenRsmModal?: () => void;
  onOpenMixtureModal?: () => void;
  onOpenTaguchiModal?: () => void;
  onOpenSampleModal?: () => void;
  onOpenImportCsvModal?: () => void;
  onOpenAboutModal?: () => void;
  onOpenPatternedModal?: () => void;
  onOpenSortModal?: () => void;
  onOpenStackModal?: () => void;
  onOpenRecodeModal?: () => void;
  onOpenSubsetModal?: () => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onOpenFactorialModal,
  onOpenRsmModal,
  onOpenMixtureModal,
  onOpenTaguchiModal,
  onOpenSampleModal,
  onOpenImportCsvModal,
  onOpenAboutModal,
  onOpenPatternedModal,
  onOpenSortModal,
  onOpenStackModal,
  onOpenRecodeModal,
  onOpenSubsetModal,
}) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const { plugins, openDialog } = usePluginStore();
  const { getActiveWorksheet } = useWorksheetStore();

  // Focus input on open
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
    }
  }, [isOpen]);

  // Build unified searchable command list
  const allCommands = useMemo<CommandItem[]>(() => {
    const list: CommandItem[] = [];

    // 1. File Operations
    list.push(
      {
        id: 'file-new',
        title: 'New Project',
        category: 'File',
        shortcut: 'Ctrl+N',
        description: 'Create a new blank project and reset session output',
        icon: <DocumentAddRegular className="text-[#008450]" />,
        action: () => {
          onClose();
          guardUnsavedChanges(() => useWorksheetStore.getState().createNewProject(), 'creating a new project', 'New Project');
        },
      },
      {
        id: 'file-save',
        title: 'Save Project (.ltb)',
        category: 'File',
        shortcut: 'Ctrl+S',
        description: 'Save worksheets, session reports, and charts into native LibRE Tab Project file',
        icon: <SaveRegular className="text-[#008450]" />,
        action: () => {
          saveProjectLtb(false);
          onClose();
        },
      },
      {
        id: 'file-save-as',
        title: 'Save Project As (.ltb)...',
        category: 'File',
        shortcut: 'Ctrl+Shift+S',
        description: 'Save project copy to a new file location',
        icon: <SaveRegular className="text-[#008450]" />,
        action: () => {
          saveProjectLtb(true);
          onClose();
        },
      },
      {
        id: 'file-open',
        title: 'Open Project / Data (.ltb, .xlsx, .csv)...',
        category: 'File',
        shortcut: 'Ctrl+O',
        description: 'Open native project or tabular workbook file',
        icon: <FolderOpenRegular className="text-[#0f6cbd]" />,
        action: () => {
          onClose();
          guardUnsavedChanges(() => openProjectFileDialog(), 'opening another file', 'Open Project');
        },
      },
      {
        id: 'file-print-pdf',
        title: 'Print / Export PDF Report...',
        category: 'File',
        shortcut: 'Ctrl+P',
        description: 'Print or export formatted statistical analysis report to PDF',
        icon: <PrintRegular className="text-[#881798]" />,
        action: () => {
          printSessionReport();
          onClose();
        },
      },
      {
        id: 'file-import-xlsx',
        title: 'Import Excel Workbook (.xlsx, .xls)...',
        category: 'File',
        shortcut: 'Ctrl+I',
        description: 'Import multi-sheet Excel spreadsheet',
        icon: <DocumentArrowDownRegular className="text-[#107c41]" />,
        action: () => {
          onClose();
          guardUnsavedChanges(() => openProjectFileDialog(), 'importing an Excel file', 'Import Excel');
        },
      },
      {
        id: 'file-import-csv',
        title: 'Import CSV / Text Data...',
        category: 'File',
        description: 'Import comma, tab, or custom delimited dataset',
        icon: <DocumentArrowDownRegular className="text-[#107c41]" />,
        action: () => {
          onClose();
          guardUnsavedChanges(() => onOpenImportCsvModal?.(), 'importing CSV data', 'Import CSV');
        },
      },
      {
        id: 'file-export-xlsx',
        title: 'Export Excel Workbook (.xlsx)...',
        category: 'File',
        shortcut: 'Ctrl+E',
        description: 'Export all worksheets to Excel workbook',
        icon: <DocumentArrowUpRegular className="text-[#107c41]" />,
        action: () => {
          exportProjectXlsx();
          onClose();
        },
      }
    );


    // 2. DOE Design Generators
    list.push(
      {
        id: 'doe-factorial',
        title: 'Create Factorial Design (2-Level Full / Fractional / Plackett-Burman)',
        category: 'DOE',
        description: 'Generate 2 to 15 factor factorial experiment matrices with randomization',
        icon: <SparkleRegular className="text-[#881798]" />,
        action: () => {
          onOpenFactorialModal?.();
          onClose();
        },
      },
      {
        id: 'doe-rsm',
        title: 'Create Response Surface Design (CCD / Box-Behnken)',
        category: 'DOE',
        description: 'Generate Central Composite or Box-Behnken second-order response surface designs',
        icon: <SparkleRegular className="text-[#881798]" />,
        action: () => {
          onOpenRsmModal?.();
          onClose();
        },
      },
      {
        id: 'doe-mixture',
        title: 'Create Mixture Design (Simplex Lattice / Centroid)',
        category: 'DOE',
        description: 'Generate simplex lattice, centroid, or extreme vertices formulations',
        icon: <SparkleRegular className="text-[#881798]" />,
        action: () => {
          onOpenMixtureModal?.();
          onClose();
        },
      },
      {
        id: 'doe-taguchi',
        title: 'Create Taguchi Robust Design (L4 to L36 Orthogonal Arrays)',
        category: 'DOE',
        description: 'Generate orthogonal arrays with Signal-to-Noise ratio metrics',
        icon: <SparkleRegular className="text-[#881798]" />,
        action: () => {
          onOpenTaguchiModal?.();
          onClose();
        },
      }
    );

    // 3. Data Suite Operations
    list.push(
      {
        id: 'data-patterned',
        title: 'Generate Patterned Data (Numeric Sequences / Arbitrary Text)',
        category: 'Data',
        description: 'Fill sequences, repeated values, arithmetic series',
        icon: <BranchForkRegular className="text-[#008450]" />,
        action: () => {
          onOpenPatternedModal?.();
          onClose();
        },
      },
      {
        id: 'data-sort',
        title: 'Sort Worksheet / Selected Columns...',
        category: 'Data',
        description: 'Multi-column nested ascending/descending sorting',
        icon: <ArrowSortRegular className="text-[#0f6cbd]" />,
        action: () => {
          onOpenSortModal?.();
          onClose();
        },
      },
      {
        id: 'data-stack',
        title: 'Stack / Unstack Columns...',
        category: 'Data',
        description: 'Reshape between wide and tall tidy format with subscript columns',
        icon: <LayerDiagonalRegular className="text-[#881798]" />,
        action: () => {
          onOpenStackModal?.();
          onClose();
        },
      },
      {
        id: 'data-recode',
        title: 'Recode Data (Values & Range Rules)...',
        category: 'Data',
        description: 'Categorize, bin continuous ranges, or map values',
        icon: <TextGrammarErrorRegular className="text-[#d83b01]" />,
        action: () => {
          onOpenRecodeModal?.();
          onClose();
        },
      },
      {
        id: 'data-subset',
        title: 'Subset Worksheet (Filter Rows)...',
        category: 'Data',
        description: 'Extract rows matching conditions into a new worksheet',
        icon: <FilterRegular className="text-[#008450]" />,
        action: () => {
          onOpenSubsetModal?.();
          onClose();
        },
      }
    );

    // 4. Sample Datasets & About
    list.push(
      {
        id: 'help-sample-data',
        title: 'Open Sample Datasets / Tutorials...',
        category: 'Help',
        description: 'Load pre-configured Six Sigma, SPC, and DOE reference datasets',
        icon: <TableRegular className="text-[#008450]" />,
        action: () => {
          onClose();
          guardUnsavedChanges(() => onOpenSampleModal?.(), 'loading a sample dataset', 'Open Sample Dataset');
        },
      },
      {
        id: 'help-about',
        title: 'About LibRE Tab...',
        category: 'Help',
        description: 'Version info, engine architecture, and statistical capabilities',
        icon: <InfoRegular className="text-[#0f6cbd]" />,
        action: () => {
          onOpenAboutModal?.();
          onClose();
        },
      }
    );

    // 5. All 122 Auto-Discovered Statistical & Analytical Plugins
    plugins.forEach((p) => {
      const cat = (p.menu_path && p.menu_path.length > 0) ? p.menu_path[0] : 'Stat';
      const pathLabel = p.menu_path ? p.menu_path.join(' > ') : cat;
      list.push({
        id: `plugin-${p.id}`,
        title: p.name,
        category: cat,
        description: `${pathLabel} • ${p.description || ''}`,
        icon: <DataBarVerticalRegular className="text-[#008450]" />,
        action: () => {
          openDialog(p.id);
          onClose();
        },
      });
    });


    return list;
  }, [plugins, openDialog, onClose]);

  // Filter commands based on user query
  const filteredCommands = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return allCommands.slice(0, 40); // Show top 40 defaults when empty

    return allCommands.filter((cmd) => {
      return (
        cmd.title.toLowerCase().includes(q) ||
        cmd.category.toLowerCase().includes(q) ||
        (cmd.description && cmd.description.toLowerCase().includes(q))
      );
    });
  }, [allCommands, query]);

  // Keyboard navigation inside palette
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < filteredCommands.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : filteredCommands.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredCommands[selectedIndex]) {
        filteredCommands[selectedIndex].action();
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  };

  // Scroll selected item into view
  useEffect(() => {
    if (listRef.current) {
      const selectedEl = listRef.current.children[selectedIndex] as HTMLElement;
      if (selectedEl) {
        selectedEl.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [selectedIndex]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] bg-black/40 backdrop-blur-xs select-none animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl bg-white rounded-xl shadow-2xl border border-[#d2d0ce] overflow-hidden flex flex-col max-h-[75vh]"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Search Header */}
        <div className="flex items-center px-4 py-3 border-b border-[#edebe9] gap-3 bg-[#faf9f8]">
          <SearchRegular className="w-5 h-5 text-[#008450] shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Type a tool name, analysis, DOE wizard, or action (e.g. 'ANOVA', 'Capability', 'Gage', 'Save')..."
            className="flex-1 bg-transparent border-none outline-none text-sm text-[#201f1e] placeholder-[#a19f9d]"
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="p-1 hover:bg-[#edebe9] rounded text-[#605e5c]"
            >
              <DismissRegular className="w-4 h-4" />
            </button>
          )}
          <span className="px-1.5 py-0.5 text-[10px] font-medium bg-[#edebe9] text-[#605e5c] rounded border border-[#d2d0ce]">
            ESC
          </span>
        </div>

        {/* Results List */}
        <div ref={listRef} className="flex-1 overflow-y-auto p-2 divide-y divide-transparent">
          {filteredCommands.length === 0 ? (
            <div className="py-12 text-center text-[#8a8886] text-sm">
              No matching statistical tools or commands found for "{query}".
            </div>
          ) : (
            filteredCommands.map((cmd, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={cmd.id}
                  onClick={() => cmd.action()}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
                    isSelected ? 'bg-[#008450] text-white shadow-xs' : 'hover:bg-[#f3f2f1] text-[#201f1e]'
                  }`}
                >
                  <div className="flex items-center space-x-3 min-w-0 pr-2">
                    <span className={`shrink-0 ${isSelected ? 'text-white' : ''}`}>
                      {cmd.icon}
                    </span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-semibold truncate ${isSelected ? 'text-white' : 'text-[#201f1e]'}`}>
                          {cmd.title}
                        </span>
                        <span
                          className={`text-[10px] px-1.5 py-0.2 rounded font-medium ${
                            isSelected
                              ? 'bg-white/20 text-white'
                              : 'bg-[#edebe9] text-[#605e5c]'
                          }`}
                        >
                          {cmd.category}
                        </span>
                      </div>
                      {cmd.description && (
                        <p className={`text-[11px] truncate mt-0.5 ${isSelected ? 'text-white/80' : 'text-[#605e5c]'}`}>
                          {cmd.description}
                        </p>
                      )}
                    </div>
                  </div>

                  {cmd.shortcut && (
                    <kbd
                      className={`text-[10px] font-mono px-2 py-0.5 rounded shrink-0 border ${
                        isSelected
                          ? 'bg-white/20 text-white border-white/30'
                          : 'bg-[#faf9f8] text-[#605e5c] border-[#d2d0ce]'
                      }`}
                    >
                      {cmd.shortcut}
                    </kbd>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer Navigation Hints */}
        <div className="px-4 py-2 border-t border-[#edebe9] bg-[#faf9f8] text-[11px] text-[#605e5c] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span>
              <kbd className="px-1.5 py-0.5 bg-[#edebe9] border border-[#d2d0ce] rounded text-[10px]">↑</kbd>{' '}
              <kbd className="px-1.5 py-0.5 bg-[#edebe9] border border-[#d2d0ce] rounded text-[10px]">↓</kbd> Navigate
            </span>
            <span>
              <kbd className="px-1.5 py-0.5 bg-[#edebe9] border border-[#d2d0ce] rounded text-[10px]">↵</kbd> Select
            </span>
            <span>
              <kbd className="px-1.5 py-0.5 bg-[#edebe9] border border-[#d2d0ce] rounded text-[10px]">ESC</kbd> Close
            </span>
          </div>
          <span className="font-medium text-[#008450]">
            {filteredCommands.length} {filteredCommands.length === 1 ? 'result' : 'results'}
          </span>
        </div>
      </div>
    </div>
  );
};

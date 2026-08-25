import React, { useEffect, useRef, useState } from 'react';
import { usePluginStore } from './store/usePluginStore';
import { TopMenu } from './components/layout/TopMenu';
import { RibbonToolbar } from './components/layout/RibbonToolbar';
import { Navigator } from './components/layout/Navigator';
import { StatusBar } from './components/layout/StatusBar';
import { SessionPane } from './components/session/SessionPane';
import { WorksheetGrid } from './components/worksheet/WorksheetGrid';
import { SheetTabBar } from './components/worksheet/SheetTabBar';
import { FormulaBar } from './components/worksheet/FormulaBar';
import { DynamicDialog } from './components/dialogs/DynamicDialog';
import { FactorialCreateModal } from './components/dialogs/FactorialCreateModal';
import { RsmCreateModal } from './components/dialogs/RsmCreateModal';
import { MixtureCreateModal } from './components/dialogs/MixtureCreateModal';
import { TaguchiCreateModal } from './components/dialogs/TaguchiCreateModal';
import { SampleDataModal } from './components/dialogs/SampleDataModal';
import { ImportCsvModal } from './components/dialogs/ImportExportModal';
import { AboutModal } from './components/dialogs/AboutModal';
import { PatternedDataModal } from './components/dialogs/PatternedDataModal';
import { SortDataModal } from './components/dialogs/SortDataModal';
import { StackUnstackModal } from './components/dialogs/StackUnstackModal';
import { RecodeModal } from './components/dialogs/RecodeModal';
import { SubsetWorksheetModal } from './components/dialogs/SubsetWorksheetModal';
import { UnsavedChangesModal } from './components/dialogs/UnsavedChangesModal';
import { CommandPalette } from './components/common/CommandPalette';
import { useWorksheetStore } from './store/useWorksheetStore';
import { useUndoRedoShortcuts } from './hooks/useUndoRedoShortcuts';
import { guardUnsavedChanges } from './hooks/useUnsavedGuard';

import { handleImportProjectFile } from './utils/projectIo';
import { startHeartbeatMonitor } from './services/api';

export const App: React.FC = () => {
  const { loadManifest, openDialog } = usePluginStore();
  const { getActiveWorksheet, isDirty } = useWorksheetStore();
  const activeSheet = getActiveWorksheet();

  // Dynamic window title: LibRE Sigma - [Project Title] (* if unsaved)
  useEffect(() => {
    const projectName = activeSheet?.name || 'Untitled Project';
    document.title = `LibRE Sigma - ${projectName}${isDirty ? ' *' : ''}`;
  }, [activeSheet?.name, isDirty]);

  // Global Undo/Redo/File keyboard shortcuts (Ctrl+Z, Ctrl+Y, Ctrl+N, Ctrl+S, Ctrl+O, Ctrl+I, Ctrl+E)
  useUndoRedoShortcuts();

  // Guard drag & drop file imports
  const handleGlobalDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      guardUnsavedChanges(
        () => handleImportProjectFile(file),
        'importing a file',
        'Import File'
      );
    }
  };

  // Window Close Guard: Standard Web / WebView beforeunload
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (useWorksheetStore.getState().isDirty) {
        e.preventDefault();
        e.returnValue = '';
        return '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  // Window Close Guard: Tauri Desktop window close requested
  useEffect(() => {
    let unlisten: (() => void) | undefined;
    const setupTauriCloseHandler = async () => {
      try {
        const { appWindow } = await import('@tauri-apps/api/window');
        unlisten = await appWindow.onCloseRequested(async (event) => {
          if (useWorksheetStore.getState().isDirty) {
            event.preventDefault();
            guardUnsavedChanges(
              async () => {
                useWorksheetStore.getState().setIsDirty(false);
                await appWindow.close();
              },
              'closing LibRE Sigma',
              'Exit LibRE Sigma'
            );
          }
        });
      } catch {
        // Tauri not present (standard web dev mode)
      }
    };
    setupTauriCloseHandler();
    return () => {
      if (unlisten) unlisten();
    };
  }, []);

  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [sampleModalOpen, setSampleModalOpen] = useState(false);
  const [importCsvModalOpen, setImportCsvModalOpen] = useState(false);
  const [aboutModalOpen, setAboutModalOpen] = useState(false);

  // Global Ctrl+K / Cmd+K listener for Universal Command Palette
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Disable default browser/webview context menu globally
  useEffect(() => {
    const handleContextMenu = (e: MouseEvent) => {
      e.preventDefault();
    };
    window.addEventListener('contextmenu', handleContextMenu);
    return () => window.removeEventListener('contextmenu', handleContextMenu);
  }, []);


  // Data Manipulation Modals
  const [patternedModalOpen, setPatternedModalOpen] = useState(false);
  const [sortModalOpen, setSortModalOpen] = useState(false);
  const [stackModalOpen, setStackModalOpen] = useState(false);
  const [unstackModalOpen, setUnstackModalOpen] = useState(false);
  const [recodeModalOpen, setRecodeModalOpen] = useState(false);
  const [subsetModalOpen, setSubsetModalOpen] = useState(false);

  // Resizable split panel between Session Output and Worksheet Grid
  const [sessionPaneHeight, setSessionPaneHeight] = useState<number>(320);

  const [isDraggingSplit, setIsDraggingSplit] = useState(false);
  const mainAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadManifest();
    const stopHeartbeat = startHeartbeatMonitor(2500);
    return () => {
      stopHeartbeat();
    };
  }, [loadManifest]);

  const handleMouseDownSplit = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDraggingSplit(true);
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDraggingSplit || !mainAreaRef.current) return;
      const rect = mainAreaRef.current.getBoundingClientRect();
      const newHeight = Math.max(120, Math.min(rect.height - 140, e.clientY - rect.top));
      setSessionPaneHeight(newHeight);
    };

    const handleMouseUp = () => {
      setIsDraggingSplit(false);
    };

    if (isDraggingSplit) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDraggingSplit]);

  return (
    <div
      className="h-screen w-screen flex flex-col bg-[#f3f2f1] overflow-hidden font-sans"
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleGlobalDrop}
    >

      {/* 1. Top Menu & Ribbon Toolbar — select-none kept here since they are pure UI controls */}
      <div className="select-none">
        <TopMenu
          onOpenSampleModal={() => setSampleModalOpen(true)}
          onOpenImportCsvModal={() => setImportCsvModalOpen(true)}
          onOpenAboutModal={() => setAboutModalOpen(true)}
          onOpenPatternedModal={() => setPatternedModalOpen(true)}
          onOpenSortModal={() => setSortModalOpen(true)}
          onOpenStackModal={() => setStackModalOpen(true)}
          onOpenUnstackModal={() => setUnstackModalOpen(true)}
          onOpenRecodeModal={() => setRecodeModalOpen(true)}
          onOpenSubsetModal={() => setSubsetModalOpen(true)}
        />
        <RibbonToolbar
          onOpenSampleModal={() => setSampleModalOpen(true)}
          onOpenImportCsvModal={() => setImportCsvModalOpen(true)}
          onOpenCommandPalette={() => setCommandPaletteOpen(true)}
        />

      </div>

      {/* Main Workspace Area (Navigator on Left, Main Split on Right) */}
      <div className="flex-1 flex overflow-hidden">
        {/* 2. Left Navigator Sidebar */}
        <Navigator />

        {/* 3 & 4. Right Workspace: Resizable Vertical Split (Session Output + Worksheet Grid) */}
        <div ref={mainAreaRef} className="flex-1 flex flex-col overflow-hidden bg-[#faf9f8] relative">
          {/* Upper Session Output Pane */}
          <div
            style={{ height: `${sessionPaneHeight}px` }}
            className="w-full shrink-0 overflow-hidden"
          >
            <SessionPane />
          </div>

          {/* Resizer Divider Bar */}
          <div
            onMouseDown={handleMouseDownSplit}
            className={`h-1.5 bg-[#edebe9] hover:bg-[#0f6cbd] cursor-row-resize flex items-center justify-center transition-colors z-10 border-y border-[#d2d0ce] ${
              isDraggingSplit ? 'bg-[#0f6cbd]' : ''
            }`}
            title="Drag to resize Session Output / Worksheet Grid"
          >
            <div className="w-8 h-0.5 bg-[#a19f9d] rounded"></div>
          </div>

          {/* Lower Worksheet Grid, Formula Bar & Tabs */}
          <div className="flex-1 flex flex-col overflow-hidden bg-white">
            {/* Dynamic Formula / Calculation Bar */}
            <FormulaBar />

            <div className="flex-1 flex flex-col overflow-hidden w-full h-full min-h-0">
              <WorksheetGrid />
            </div>
            <SheetTabBar />
          </div>
        </div>
      </div>

      {/* Bottom Status Bar */}
      <StatusBar />

      {/* Dynamic Dialog Engine & DOE Modals */}
      <DynamicDialog />
      <FactorialCreateModal />
      <RsmCreateModal />
      <MixtureCreateModal />
      <TaguchiCreateModal />

      {/* Data Manipulation Modals */}
      <PatternedDataModal
        open={patternedModalOpen}
        onClose={() => setPatternedModalOpen(false)}
      />
      <SortDataModal
        open={sortModalOpen}
        onClose={() => setSortModalOpen(false)}
      />
      <StackUnstackModal
        open={stackModalOpen}
        mode="stack"
        onClose={() => setStackModalOpen(false)}
      />
      <StackUnstackModal
        open={unstackModalOpen}
        mode="unstack"
        onClose={() => setUnstackModalOpen(false)}
      />
      <RecodeModal
        open={recodeModalOpen}
        onClose={() => setRecodeModalOpen(false)}
      />
      <SubsetWorksheetModal
        open={subsetModalOpen}
        onClose={() => setSubsetModalOpen(false)}
      />

      {/* Additional Modals */}
      <SampleDataModal
        isOpen={sampleModalOpen}
        onClose={() => setSampleModalOpen(false)}
      />
      <ImportCsvModal
        isOpen={importCsvModalOpen}
        onClose={() => setImportCsvModalOpen(false)}
      />
      <AboutModal
        isOpen={aboutModalOpen}
        onClose={() => setAboutModalOpen(false)}
      />

      {/* Unsaved Changes Warning Modal */}
      <UnsavedChangesModal />

      {/* Universal Command Palette (Ctrl+K) */}
      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        onOpenFactorialModal={() => openDialog('doe_create_factorial')}
        onOpenRsmModal={() => openDialog('doe_create_rsm')}
        onOpenMixtureModal={() => openDialog('doe_create_mixture')}
        onOpenTaguchiModal={() => openDialog('doe_create_taguchi')}
        onOpenSampleModal={() => setSampleModalOpen(true)}
        onOpenImportCsvModal={() => setImportCsvModalOpen(true)}
        onOpenAboutModal={() => setAboutModalOpen(true)}
        onOpenPatternedModal={() => setPatternedModalOpen(true)}
        onOpenSortModal={() => setSortModalOpen(true)}
        onOpenStackModal={() => setStackModalOpen(true)}
        onOpenRecodeModal={() => setRecodeModalOpen(true)}
        onOpenSubsetModal={() => setSubsetModalOpen(true)}
      />
    </div>
  );
};

export default App;


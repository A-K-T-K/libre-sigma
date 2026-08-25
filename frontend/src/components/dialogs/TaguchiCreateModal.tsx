import React, { useEffect, useState } from 'react';
import {
  Button,
  Input,
  Badge,
  Spinner,
  Table,
  TableHeader,
  TableHeaderCell,
  TableBody,
  TableRow,
  TableCell,
  Field,
} from '@fluentui/react-components';
import {
  SparkleRegular,
  DismissRegular,
  TableRegular,
  OptionsRegular,
  DocumentBulletListRegular,
  InfoRegular,
} from '@fluentui/react-icons';
import { usePluginStore } from '../../store/usePluginStore';

interface ArrayDef {
  id: string;
  name: string;
  runs: number;
  max_factors: number;
  levels: number | string;
  type: string;
  desc: string;
}

const ALL_TAGUCHI_ARRAYS: ArrayDef[] = [
  { id: 'L4_2_3', name: 'L4 (2^3)', runs: 4, max_factors: 3, levels: 2, type: '2_level', desc: '4 Runs, 2 to 3 Factors' },
  { id: 'L8_2_7', name: 'L8 (2^7)', runs: 8, max_factors: 7, levels: 2, type: '2_level', desc: '8 Runs, 2 to 7 Factors' },
  { id: 'L12_2_11', name: 'L12 (2^11)', runs: 12, max_factors: 11, levels: 2, type: '2_level', desc: '12 Runs, 2 to 11 Factors' },
  { id: 'L16_2_15', name: 'L16 (2^15)', runs: 16, max_factors: 15, levels: 2, type: '2_level', desc: '16 Runs, 2 to 15 Factors' },
  { id: 'L32_2_31', name: 'L32 (2^31)', runs: 32, max_factors: 31, levels: 2, type: '2_level', desc: '32 Runs, 2 to 31 Factors' },

  { id: 'L9_3_4', name: 'L9 (3^4)', runs: 9, max_factors: 4, levels: 3, type: '3_level', desc: '9 Runs, 2 to 4 Factors' },
  { id: 'L27_3_13', name: 'L27 (3^13)', runs: 27, max_factors: 13, levels: 3, type: '3_level', desc: '27 Runs, 2 to 13 Factors' },

  { id: 'L16_4_5', name: 'L16 (4^5)', runs: 16, max_factors: 5, levels: 4, type: '4_level', desc: '16 Runs, 2 to 5 Factors' },
  { id: 'L32_4_9', name: 'L32 (4^9)', runs: 32, max_factors: 9, levels: 4, type: '4_level', desc: '32 Runs, 2 to 9 Factors' },

  { id: 'L25_5_6', name: 'L25 (5^6)', runs: 25, max_factors: 6, levels: 5, type: '5_level', desc: '25 Runs, 2 to 6 Factors' },
  { id: 'L50_5_11', name: 'L50 (5^11)', runs: 50, max_factors: 11, levels: 5, type: '5_level', desc: '50 Runs, 2 to 11 Factors' },

  { id: 'L18_2_1_3_7', name: 'L18 (2^1 x 3^7)', runs: 18, max_factors: 8, levels: '2, 3', type: 'mixed', desc: '18 Runs, 1 2-Level & 7 3-Level Factors' },
  { id: 'L36_2_11_3_12', name: 'L36 (2^11 x 3^12)', runs: 36, max_factors: 13, levels: '2, 3', type: 'mixed', desc: '36 Runs, 2 to 13 Mixed Factors' },
];

const DESIGN_TYPE_CONFIG: Record<string, { label: string; rangeText: string; maxAllowedFactors: number; defaultArray: string }> = {
  '2_level': { label: '2-Level Design', rangeText: '(2 to 31 factors)', maxAllowedFactors: 31, defaultArray: 'L8_2_7' },
  '3_level': { label: '3-Level Design', rangeText: '(2 to 13 factors)', maxAllowedFactors: 13, defaultArray: 'L9_3_4' },
  '4_level': { label: '4-Level Design', rangeText: '(2 to 9 factors)', maxAllowedFactors: 9, defaultArray: 'L16_4_5' },
  '5_level': { label: '5-Level Design', rangeText: '(2 to 11 factors)', maxAllowedFactors: 11, defaultArray: 'L25_5_6' },
  'mixed': { label: 'Mixed Level Design', rangeText: '(2 to 26 factors)', maxAllowedFactors: 26, defaultArray: 'L18_2_1_3_7' },
};

export const TaguchiCreateModal: React.FC = () => {
  const { activePluginId, closeDialog, runCompute, isComputing, computeError } = usePluginStore();

  const [factorType, setFactorType] = useState<string>('3_level');
  const [numFactors, setNumFactors] = useState<number>(3);
  const [selectedArrayId, setSelectedArrayId] = useState<string>('L9_3_4');
  const [factorNames, setFactorNames] = useState<string[]>(['A', 'B', 'C']);
  const [factorLevels, setFactorLevels] = useState<Record<number, string[]>>({
    0: ['1', '2', '3'],
    1: ['1', '2', '3'],
    2: ['1', '2', '3'],
  });
  const [worksheetName, setWorksheetName] = useState<string>('Taguchi Design');

  // Sub-dialogs state
  const [showDesignsModal, setShowDesignsModal] = useState<boolean>(false);
  const [showFactorsModal, setShowFactorsModal] = useState<boolean>(false);
  const [showOptionsModal, setShowOptionsModal] = useState<boolean>(false);
  const [showResultsModal, setShowResultsModal] = useState<boolean>(false);

  const isOpen = activePluginId === 'doe_create_taguchi';

  const getLevelCountForFactor = (fIdx: number): number => {
    if (factorType === '2_level') return 2;
    if (factorType === '3_level') return 3;
    if (factorType === '4_level') return 4;
    if (factorType === '5_level') return 5;
    if (factorType === 'mixed') return fIdx === 0 ? 2 : 3;
    return 3;
  };

  // When factor type changes, update default factor count and available array
  useEffect(() => {
    const cfg = DESIGN_TYPE_CONFIG[factorType];
    if (cfg) {
      const defaultK = Math.min(3, cfg.maxAllowedFactors);
      setNumFactors(defaultK);
      setSelectedArrayId(cfg.defaultArray);
      const names = Array.from({ length: defaultK }, (_, i) => String.fromCharCode(65 + i));
      setFactorNames(names);

      const newLevels: Record<number, string[]> = {};
      for (let i = 0; i < defaultK; i++) {
        const lvlCount = factorType === '2_level' ? 2 : factorType === '3_level' ? 3 : factorType === '4_level' ? 4 : factorType === '5_level' ? 5 : i === 0 ? 2 : 3;
        newLevels[i] = Array.from({ length: lvlCount }, (_, lIdx) => String(lIdx + 1));
      }
      setFactorLevels(newLevels);
    }
  }, [factorType]);

  // When numFactors changes, update factor names array and array selection
  const handleNumFactorsChange = (newK: number) => {
    setNumFactors(newK);
    setFactorNames((prev) => {
      const updated = [...prev];
      while (updated.length < newK) {
        updated.push(String.fromCharCode(65 + updated.length));
      }
      return updated.slice(0, newK);
    });

    setFactorLevels((prev) => {
      const updated = { ...prev };
      for (let i = 0; i < newK; i++) {
        const lvlCount = getLevelCountForFactor(i);
        if (!updated[i] || updated[i].length !== lvlCount) {
          updated[i] = Array.from({ length: lvlCount }, (_, lIdx) => String(lIdx + 1));
        }
      }
      return updated;
    });

    // Auto select suitable array if current array cannot accommodate new factor count
    const suitable = ALL_TAGUCHI_ARRAYS.filter((a) => a.type === factorType && a.max_factors >= newK);
    const curArray = suitable.find((a) => a.id === selectedArrayId);
    if (!curArray && suitable.length > 0) {
      const smallestFit = [...suitable].sort((a, b) => a.runs - b.runs)[0];
      setSelectedArrayId(smallestFit.id);
    }
  };

  if (!isOpen) return null;

  const currentConfig = DESIGN_TYPE_CONFIG[factorType] || DESIGN_TYPE_CONFIG['3_level'];
  const compatibleArrays = ALL_TAGUCHI_ARRAYS.filter(
    (a) => a.type === factorType && a.max_factors >= numFactors
  );
  const selectedArray =
    compatibleArrays.find((a) => a.id === selectedArrayId) ||
    compatibleArrays[0] ||
    ALL_TAGUCHI_ARRAYS.find((a) => a.type === factorType) ||
    ALL_TAGUCHI_ARRAYS[0];

  const handleGenerate = async () => {
    const arrayToUse = selectedArray?.id || selectedArrayId || 'L9_3_4';
    const sheetTitle = worksheetName.trim() || `Taguchi ${selectedArray?.name || 'Design'}`;

    // Build factor levels mapping
    const levelsMap: Record<string, string[]> = {};
    for (let i = 0; i < numFactors; i++) {
      const fname = factorNames[i] || String.fromCharCode(65 + i);
      levelsMap[fname] = factorLevels[i] || Array.from({ length: getLevelCountForFactor(i) }, (_, l) => String(l + 1));
    }

    const success = await runCompute('doe_create_taguchi', {
      factor_type: factorType,
      array_choice: arrayToUse,
      num_factors: Number(numFactors),
      factor_names_str: factorNames.slice(0, numFactors).join(', '),
      factor_levels_json: JSON.stringify(levelsMap),
      worksheet_name: sheetTitle,
    });
    if (success) {
      closeDialog();
    }
  };

  return (
    <>
      {/* 1. PRIMARY MODAL: Create Taguchi Orthogonal Design */}
      <div
        className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-[1px] p-4 select-none animate-in fade-in duration-100"
        onClick={(e) => {
          if (e.target === e.currentTarget) closeDialog();
        }}
      >
        <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-full max-w-lg overflow-hidden flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-100">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3.5 bg-[#f8f9fa] border-b border-[#e0e0e0]">
            <div className="flex items-center space-x-2">
              <SparkleRegular className="text-[#008450]" />
              <h2 className="text-sm font-bold text-[#201f1e]">
                Create Taguchi Design
              </h2>
            </div>
            <Button
              appearance="subtle"
              size="small"
              icon={<DismissRegular />}
              onClick={closeDialog}
              style={{ minWidth: '28px', padding: 0 }}
            />
          </div>

          {/* Body */}
          <div className="p-5 space-y-4 max-h-[65vh] overflow-y-auto">
            {computeError && (
              <div className="p-2.5 bg-red-50 border border-red-200 rounded-md text-xs text-red-700 flex items-center gap-2">
                <InfoRegular className="w-4 h-4 shrink-0 text-red-600" />
                <span>{computeError}</span>
              </div>
            )}

            {/* Design Type Radio Group */}
            <div className="space-y-2 border border-[#edebe9] p-3 rounded-lg bg-[#faf9f8]">
              <label className="text-xs font-bold text-[#201f1e] block">
                Taguchi Design Type:
              </label>
              <div className="space-y-1.5 pl-1">
                {Object.entries(DESIGN_TYPE_CONFIG).map(([typeKey, cfg]) => (
                  <label
                    key={typeKey}
                    className="flex items-center space-x-2.5 cursor-pointer py-0.5 hover:text-[#008450] text-xs text-[#323130]"
                  >
                    <input
                      type="radio"
                      name="taguchi_design_type"
                      checked={factorType === typeKey}
                      onChange={() => setFactorType(typeKey)}
                      className="text-[#008450] cursor-pointer"
                    />
                    <span className="font-medium">{cfg.label}</span>
                    <span className="text-[11px] text-[#8a8886]">{cfg.rangeText}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Number of Factors Dropdown */}
            <Field label={{ children: <span className="text-xs font-semibold text-[#323130]">Number of Factors:</span> }}>
              <select
                value={numFactors}
                onChange={(e) => handleNumFactorsChange(Number(e.target.value))}
                className="w-full px-2.5 py-1.5 text-xs bg-white border border-[#d2d0ce] focus:border-[#008450] rounded-md outline-none text-[#201f1e]"
              >
                {Array.from({ length: currentConfig.maxAllowedFactors - 1 }, (_, i) => i + 2).map((k) => (
                  <option key={k} value={k}>
                    {k} Factors ({String.fromCharCode(65)} through {String.fromCharCode(65 + k - 1)})
                  </option>
                ))}
              </select>
            </Field>

            {/* Current Active Selection Summary Card */}
            <div className="p-3 bg-[#e6faf0]/70 border border-[#bbf2d6] rounded-md text-xs text-[#004d2c] space-y-1">
              <div className="font-semibold flex items-center justify-between">
                <span>Selected Design:</span>
                <span className="bg-[#008450] text-white px-2 py-0.5 rounded text-[11px] font-semibold">
                  {selectedArray.name} ({selectedArray.runs} Runs)
                </span>
              </div>
              <p className="text-[11.5px] leading-relaxed">
                Factors: <strong>{numFactors}</strong> ({factorNames.slice(0, numFactors).join(', ')}) • Levels: <strong>{selectedArray.levels}</strong> • Columns Used: <strong>1 to {numFactors}</strong>
              </p>
            </div>

            {/* Sub-modal Action Buttons */}
            <div className="grid grid-cols-4 gap-2 pt-2 border-t border-[#edebe9]">
              <Button
                appearance="secondary"
                size="small"
                icon={<TableRegular className="text-[#008450]" />}
                onClick={() => setShowDesignsModal(true)}
              >
                Designs...
              </Button>
              <Button
                appearance="secondary"
                size="small"
                icon={<DocumentBulletListRegular className="text-[#008450]" />}
                onClick={() => setShowFactorsModal(true)}
              >
                Factors...
              </Button>
              <Button
                appearance="secondary"
                size="small"
                icon={<OptionsRegular className="text-[#008450]" />}
                onClick={() => setShowOptionsModal(true)}
              >
                Options...
              </Button>
              <Button
                appearance="secondary"
                size="small"
                icon={<InfoRegular className="text-[#008450]" />}
                onClick={() => setShowResultsModal(true)}
              >
                Results...
              </Button>
            </div>
          </div>

          {/* Footer */}
          <div className="px-5 py-3 bg-[#f8f9fa] border-t border-[#e0e0e0] flex items-center justify-end space-x-2">
            <Button appearance="secondary" size="medium" onClick={closeDialog}>
              Cancel
            </Button>
            <Button
              appearance="primary"
              size="medium"
              onClick={handleGenerate}
              disabled={isComputing}
              icon={isComputing ? <Spinner size="tiny" /> : undefined}
            >
              {isComputing ? 'Generating...' : 'OK'}
            </Button>
          </div>
        </div>
      </div>

      {/* 2. SUB-MODAL: [Designs...] Orthogonal Arrays Catalog & Selector */}
      {showDesignsModal && (
        <div
          className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 backdrop-blur-[1px] p-4 select-none animate-in fade-in duration-100"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowDesignsModal(false);
          }}
        >
          <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-full max-w-2xl overflow-hidden flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-100">
            <div className="flex items-center justify-between px-5 py-3.5 bg-[#f8f9fa] border-b border-[#e0e0e0]">
              <div className="flex items-center gap-2">
                <TableRegular className="text-[#008450]" />
                <h3 className="text-sm font-bold text-[#201f1e]">
                  Available Taguchi Orthogonal Arrays ({numFactors} Factors, {currentConfig.label})
                </h3>
              </div>
              <Button
                appearance="subtle"
                size="small"
                icon={<DismissRegular />}
                onClick={() => setShowDesignsModal(false)}
              />
            </div>

            <div className="p-5 space-y-4 overflow-y-auto max-h-[60vh]">
              <div className="border border-[#e0e0e0] rounded-lg overflow-hidden">
                <Table size="small">
                  <TableHeader>
                    <TableRow className="bg-[#f0f0f0]">
                      <TableHeaderCell style={{ fontWeight: 700 }}>Array</TableHeaderCell>
                      <TableHeaderCell style={{ fontWeight: 700, textAlign: 'center' }}>Runs</TableHeaderCell>
                      <TableHeaderCell style={{ fontWeight: 700, textAlign: 'center' }}>Levels</TableHeaderCell>
                      <TableHeaderCell style={{ fontWeight: 700, textAlign: 'center' }}>Max Factors</TableHeaderCell>
                      <TableHeaderCell style={{ fontWeight: 700 }}>Description</TableHeaderCell>
                      <TableHeaderCell style={{ fontWeight: 700, textAlign: 'center' }}>Select</TableHeaderCell>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {ALL_TAGUCHI_ARRAYS.filter((a) => a.type === factorType).map((a) => {
                      const isSelected = selectedArrayId === a.id;
                      const isCompatible = a.max_factors >= numFactors;
                      return (
                        <TableRow
                          key={a.id}
                          onClick={() => {
                            if (isCompatible) setSelectedArrayId(a.id);
                          }}
                          className={`transition-colors ${
                            isSelected
                              ? 'bg-[#e6faf0]'
                              : isCompatible
                              ? 'cursor-pointer hover:bg-[#f5f5f5]'
                              : 'opacity-50 cursor-not-allowed bg-slate-50'
                          }`}
                        >
                          <TableCell style={{ fontWeight: 600, color: '#008450' }}>{a.name}</TableCell>
                          <TableCell style={{ textAlign: 'center' }}>{a.runs}</TableCell>
                          <TableCell style={{ textAlign: 'center' }}>{a.levels}</TableCell>
                          <TableCell style={{ textAlign: 'center' }}>{a.max_factors}</TableCell>
                          <TableCell style={{ fontSize: '11.5px', color: '#605e5c' }}>{a.desc}</TableCell>
                          <TableCell style={{ textAlign: 'center' }}>
                            <input
                              type="radio"
                              name="selected_taguchi_array"
                              checked={isSelected}
                              disabled={!isCompatible}
                              onChange={() => setSelectedArrayId(a.id)}
                              className="text-[#008450] cursor-pointer"
                            />
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </div>

            <div className="px-5 py-3 bg-[#f8f9fa] border-t border-[#e0e0e0] flex items-center justify-end">
              <Button appearance="primary" size="medium" onClick={() => setShowDesignsModal(false)}>
                OK
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 3. SUB-MODAL: [Factors...] Factors Names & Levels Editor */}
      {showFactorsModal && (
        <div
          className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 backdrop-blur-[1px] p-4 select-none animate-in fade-in duration-100"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowFactorsModal(false);
          }}
        >
          <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-full max-w-2xl overflow-hidden flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-100">
            <div className="flex items-center justify-between px-5 py-3.5 bg-[#f8f9fa] border-b border-[#e0e0e0]">
              <div className="flex items-center gap-2">
                <DocumentBulletListRegular className="text-[#008450]" />
                <h3 className="text-sm font-bold text-[#201f1e]">Taguchi Factor Names & Level Values</h3>
              </div>
              <Button
                appearance="subtle"
                size="small"
                icon={<DismissRegular />}
                onClick={() => setShowFactorsModal(false)}
              />
            </div>

            <div className="p-5 space-y-4 overflow-y-auto max-h-[60vh]">
              <div className="border border-[#e0e0e0] rounded-lg overflow-hidden">
                <Table size="small">
                  <TableHeader>
                    <TableRow className="bg-[#f0f0f0]">
                      <TableHeaderCell style={{ width: '60px', fontWeight: 700, textAlign: 'center' }}>Factor</TableHeaderCell>
                      <TableHeaderCell style={{ width: '130px', fontWeight: 700 }}>Name</TableHeaderCell>
                      <TableHeaderCell style={{ fontWeight: 700 }}>Level 1</TableHeaderCell>
                      <TableHeaderCell style={{ fontWeight: 700 }}>Level 2</TableHeaderCell>
                      {factorType !== '2_level' && <TableHeaderCell style={{ fontWeight: 700 }}>Level 3</TableHeaderCell>}
                      {(factorType === '4_level' || factorType === '5_level') && (
                        <TableHeaderCell style={{ fontWeight: 700 }}>Level 4</TableHeaderCell>
                      )}
                      {factorType === '5_level' && <TableHeaderCell style={{ fontWeight: 700 }}>Level 5</TableHeaderCell>}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Array.from({ length: numFactors }).map((_, fIdx) => {
                      const fname = factorNames[fIdx] || String.fromCharCode(65 + fIdx);
                      const fLevels = factorLevels[fIdx] || ['1', '2', '3'];
                      const lvlCount = getLevelCountForFactor(fIdx);

                      return (
                        <TableRow key={fIdx}>
                          <TableCell style={{ fontWeight: 600, color: '#008450', textAlign: 'center' }}>
                            {String.fromCharCode(65 + fIdx)}
                          </TableCell>
                          <TableCell>
                            <Input
                              size="small"
                              value={fname}
                              onChange={(_, data) => {
                                const next = [...factorNames];
                                next[fIdx] = data.value;
                                setFactorNames(next);
                              }}
                              className="w-full"
                            />
                          </TableCell>
                          {Array.from({ length: factorType === '2_level' ? 2 : factorType === '5_level' ? 5 : factorType === '4_level' ? 4 : 3 }).map((_, lIdx) => {
                            const isApplicable = lIdx < lvlCount;
                            return (
                              <TableCell key={lIdx}>
                                {isApplicable ? (
                                  <Input
                                    size="small"
                                    value={fLevels[lIdx] ?? String(lIdx + 1)}
                                    onChange={(_, data) => {
                                      const nextMap = { ...factorLevels };
                                      const currentLevels = [...(nextMap[fIdx] || Array.from({ length: lvlCount }, (__, i) => String(i + 1)))];
                                      currentLevels[lIdx] = data.value;
                                      nextMap[fIdx] = currentLevels;
                                      setFactorLevels(nextMap);
                                    }}
                                    className="w-full"
                                  />
                                ) : (
                                  <span className="text-[#a19f9d] italic text-xs">—</span>
                                )}
                              </TableCell>
                            );
                          })}
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </div>

            <div className="px-5 py-3 bg-[#f8f9fa] border-t border-[#e0e0e0] flex items-center justify-end">
              <Button appearance="primary" size="medium" onClick={() => setShowFactorsModal(false)}>
                OK
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 4. SUB-MODAL: [Options...] Taguchi Design Options */}
      {showOptionsModal && (
        <div
          className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 backdrop-blur-[1px] p-4 select-none animate-in fade-in duration-100"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowOptionsModal(false);
          }}
        >
          <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-full max-w-md overflow-hidden flex flex-col animate-in zoom-in-95 duration-100">
            <div className="flex items-center justify-between px-5 py-3.5 bg-[#f8f9fa] border-b border-[#e0e0e0]">
              <div className="flex items-center gap-2">
                <OptionsRegular className="text-[#008450]" />
                <h3 className="text-sm font-bold text-[#201f1e]">Taguchi Design Options</h3>
              </div>
              <Button
                appearance="subtle"
                size="small"
                icon={<DismissRegular />}
                onClick={() => setShowOptionsModal(false)}
              />
            </div>

            <div className="p-5 space-y-4 text-xs">
              <Field label={{ children: <span className="text-xs font-semibold">Store design in worksheet:</span> }}>
                <Input
                  size="small"
                  value={worksheetName}
                  onChange={(_, data) => setWorksheetName(data.value)}
                  className="w-full"
                />
              </Field>
            </div>

            <div className="px-5 py-3 bg-[#f8f9fa] border-t border-[#e0e0e0] flex items-center justify-end">
              <Button appearance="primary" size="medium" onClick={() => setShowOptionsModal(false)}>
                OK
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 5. SUB-MODAL: [Results...] Design Summary */}
      {showResultsModal && (
        <div
          className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 backdrop-blur-[1px] p-4 select-none animate-in fade-in duration-100"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowResultsModal(false);
          }}
        >
          <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-full max-w-md overflow-hidden flex flex-col animate-in zoom-in-95 duration-100">
            <div className="flex items-center justify-between px-5 py-3.5 bg-[#f8f9fa] border-b border-[#e0e0e0]">
              <div className="flex items-center gap-2">
                <InfoRegular className="text-[#008450]" />
                <h3 className="text-sm font-bold text-[#201f1e]">Design Summary</h3>
              </div>
              <Button
                appearance="subtle"
                size="small"
                icon={<DismissRegular />}
                onClick={() => setShowResultsModal(false)}
              />
            </div>

            <div className="p-5 space-y-3 text-xs text-[#323130]">
              <div className="bg-[#f0f0f0] p-3 rounded space-y-1.5 text-[11.5px]">
                <div>Design: Taguchi Orthogonal Array</div>
                <div>Array: {selectedArray.name} ({selectedArray.runs} Runs)</div>
                <div>Factors: {numFactors} ({factorNames.slice(0, numFactors).join(', ')})</div>
                <div>Levels per Factor: {selectedArray.levels}</div>
                <div>Array Columns Used: 1 to {numFactors}</div>
                <div>Target Worksheet: {worksheetName || `Taguchi ${selectedArray.name}`}</div>
              </div>
            </div>

            <div className="px-5 py-3 bg-[#f8f9fa] border-t border-[#e0e0e0] flex items-center justify-end">
              <Button appearance="primary" size="medium" onClick={() => setShowResultsModal(false)}>
                OK
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

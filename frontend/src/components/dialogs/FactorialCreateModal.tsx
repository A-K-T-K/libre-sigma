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

interface FactorialCatalogItem {
  factors: number;
  runs: number;
  fraction: string;
  resolution: string;
  resCode: 'III' | 'IV' | 'V' | 'Full';
}

const FACTORIAL_CATALOG: FactorialCatalogItem[] = [
  { factors: 2, runs: 4, fraction: 'Full', resolution: 'Full Factorial', resCode: 'Full' },
  { factors: 3, runs: 4, fraction: '1/2 Fraction', resolution: 'Resolution III', resCode: 'III' },
  { factors: 3, runs: 8, fraction: 'Full', resolution: 'Full Factorial', resCode: 'Full' },
  { factors: 4, runs: 8, fraction: '1/2 Fraction', resolution: 'Resolution IV', resCode: 'IV' },
  { factors: 4, runs: 16, fraction: 'Full', resolution: 'Full Factorial', resCode: 'Full' },
  { factors: 5, runs: 8, fraction: '1/4 Fraction', resolution: 'Resolution III', resCode: 'III' },
  { factors: 5, runs: 16, fraction: '1/2 Fraction', resolution: 'Resolution V', resCode: 'V' },
  { factors: 5, runs: 32, fraction: 'Full', resolution: 'Full Factorial', resCode: 'Full' },
  { factors: 6, runs: 8, fraction: '1/8 Fraction', resolution: 'Resolution III', resCode: 'III' },
  { factors: 6, runs: 16, fraction: '1/4 Fraction', resolution: 'Resolution IV', resCode: 'IV' },
  { factors: 6, runs: 32, fraction: '1/2 Fraction', resolution: 'Resolution VI', resCode: 'V' },
  { factors: 6, runs: 64, fraction: 'Full', resolution: 'Full Factorial', resCode: 'Full' },
  { factors: 7, runs: 8, fraction: '1/16 Fraction', resolution: 'Resolution III', resCode: 'III' },
  { factors: 7, runs: 16, fraction: '1/8 Fraction', resolution: 'Resolution IV', resCode: 'IV' },
  { factors: 7, runs: 32, fraction: '1/4 Fraction', resolution: 'Resolution IV', resCode: 'IV' },
  { factors: 7, runs: 64, fraction: '1/2 Fraction', resolution: 'Resolution VII', resCode: 'V' },
  { factors: 8, runs: 16, fraction: '1/16 Fraction', resolution: 'Resolution IV', resCode: 'IV' },
  { factors: 8, runs: 32, fraction: '1/8 Fraction', resolution: 'Resolution IV', resCode: 'IV' },
  { factors: 8, runs: 64, fraction: '1/4 Fraction', resolution: 'Resolution V', resCode: 'V' },
  { factors: 9, runs: 16, fraction: '1/32 Fraction', resolution: 'Resolution III', resCode: 'III' },
  { factors: 9, runs: 32, fraction: '1/16 Fraction', resolution: 'Resolution IV', resCode: 'IV' },
  { factors: 9, runs: 64, fraction: '1/8 Fraction', resolution: 'Resolution IV', resCode: 'IV' },
  { factors: 10, runs: 16, fraction: '1/64 Fraction', resolution: 'Resolution III', resCode: 'III' },
  { factors: 10, runs: 32, fraction: '1/32 Fraction', resolution: 'Resolution IV', resCode: 'IV' },
  { factors: 10, runs: 64, fraction: '1/16 Fraction', resolution: 'Resolution IV', resCode: 'IV' },
];

export const FactorialCreateModal: React.FC = () => {
  const { activePluginId, closeDialog, runCompute, isComputing, computeError } = usePluginStore();

  const [designType, setDesignType] = useState<string>('2_level');
  const [numFactors, setNumFactors] = useState<number>(3);
  const [selectedRuns, setSelectedRuns] = useState<number>(8);
  const [centerPoints, setCenterPoints] = useState<number>(0);
  const [numReplicates, setNumReplicates] = useState<number>(1);
  const [numBlocks, setNumBlocks] = useState<number>(1);
  const [randomizeRuns, setRandomizeRuns] = useState<boolean>(true);
  const [randomSeed, setRandomSeed] = useState<string>('');
  const [worksheetName, setWorksheetName] = useState<string>('Factorial Design');

  // Factors metadata
  const [factorNames, setFactorNames] = useState<string[]>(['A', 'B', 'C']);
  const [factorTypes, setFactorTypes] = useState<string[]>(['Numeric', 'Numeric', 'Numeric']);
  const [factorLows, setFactorLows] = useState<string[]>(['-1', '-1', '-1']);
  const [factorHighs, setFactorHighs] = useState<string[]>(['1', '1', '1']);
  const [generalLevels, setGeneralLevels] = useState<number[]>([2, 2, 2]);

  // Sub-modals state
  const [showDesignsModal, setShowDesignsModal] = useState<boolean>(false);
  const [showFactorsModal, setShowFactorsModal] = useState<boolean>(false);
  const [showOptionsModal, setShowOptionsModal] = useState<boolean>(false);
  const [showResultsModal, setShowResultsModal] = useState<boolean>(false);

  const isOpen = activePluginId === 'doe_create_factorial';

  // Synchronize factor names and levels on factor count change
  useEffect(() => {
    const names = Array.from({ length: numFactors }, (_, i) => String.fromCharCode(65 + i));
    setFactorNames(names);
    setFactorTypes(Array.from({ length: numFactors }, () => 'Numeric'));
    setFactorLows(Array.from({ length: numFactors }, () => '-1'));
    setFactorHighs(Array.from({ length: numFactors }, () => '1'));
    setGeneralLevels(Array.from({ length: numFactors }, () => 2));

    // Default runs
    if (designType === 'plackett_burman') {
      const pbRuns = Math.max(8, Math.ceil((numFactors + 1) / 4) * 4);
      setSelectedRuns(pbRuns);
    } else if (designType === 'general_full') {
      setSelectedRuns(Math.pow(2, numFactors));
    } else {
      const avail = FACTORIAL_CATALOG.filter((c) => c.factors === numFactors);
      if (avail.length > 0) {
        setSelectedRuns(avail[avail.length - 1].runs); // Default to full or highest resolution
      } else {
        setSelectedRuns(Math.pow(2, Math.min(numFactors, 6)));
      }
    }
  }, [numFactors, designType]);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    const payload = {
      design_type: designType,
      num_factors: numFactors,
      num_runs: selectedRuns,
      num_center_points: Number(centerPoints) || 0,
      num_replicates: Number(numReplicates) || 1,
      num_blocks: Number(numBlocks) || 1,
      factor_names_str: factorNames.slice(0, numFactors).join(', '),
      factor_lows_str: factorLows.slice(0, numFactors).join(', '),
      factor_highs_str: factorHighs.slice(0, numFactors).join(', '),
      factor_types_str: factorTypes.slice(0, numFactors).join(', '),
      general_levels_str: generalLevels.slice(0, numFactors).join(', '),
      randomize_runs: randomizeRuns,
      random_seed: randomSeed.trim() ? Number(randomSeed) : null,
      worksheet_name: worksheetName.trim() || 'Factorial Design',
    };

    const success = await runCompute('doe_create_factorial', payload);
    if (success) {
      closeDialog();
    }
  };

  const getResBadge = (resCode: string) => {
    switch (resCode) {
      case 'Full':
        return <Badge appearance="filled" style={{ backgroundColor: '#008450', color: 'white' }}>Full</Badge>;
      case 'V':
        return <Badge appearance="filled" style={{ backgroundColor: '#0078d4', color: 'white' }}>Res V+</Badge>;
      case 'IV':
        return <Badge appearance="filled" style={{ backgroundColor: '#ca5010', color: 'white' }}>Res IV</Badge>;
      case 'III':
      default:
        return <Badge appearance="filled" style={{ backgroundColor: '#d83b01', color: 'white' }}>Res III</Badge>;
    }
  };

  const availableOptionsForK = FACTORIAL_CATALOG.filter((c) => c.factors === numFactors);

  return (
    <>
      {/* 1. PRIMARY MODAL: Create Factorial Design */}
      <div
        className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-[1px] p-4 select-none animate-in fade-in duration-100"
        onClick={(e) => {
          if (e.target === e.currentTarget) closeDialog();
        }}
      >
        <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-full max-w-xl overflow-hidden flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-100 font-sans">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3.5 bg-[#f8f9fa] border-b border-[#e0e0e0]">
            <div className="flex items-center space-x-2">
              <SparkleRegular className="text-[#008450]" />
              <h2 className="text-sm font-bold text-[#201f1e]">
                Create Factorial Design
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
                Factorial Design Type:
              </label>
              <div className="space-y-1.5 pl-1">
                {[
                  { id: '2_level', label: '2-level factorial (default generator)', range: '(2 to 15 factors)' },
                  { id: 'split_plot', label: '2-level split-plot design', range: '(Hard & easy-to-change factors)' },
                  { id: 'plackett_burman', label: 'Plackett-Burman design', range: '(Screening, 2 to 47 factors)' },
                  { id: 'general_full', label: 'General full factorial design', range: '(Mixed levels: 2 to 100 levels)' },
                ].map((dt) => (
                  <label
                    key={dt.id}
                    className="flex items-center space-x-2.5 cursor-pointer py-0.5 hover:text-[#008450] text-xs text-[#323130]"
                  >
                    <input
                      type="radio"
                      name="factorial_design_type"
                      checked={designType === dt.id}
                      onChange={() => setDesignType(dt.id)}
                      className="text-[#008450] cursor-pointer"
                    />
                    <span className="font-medium">{dt.label}</span>
                    <span className="text-[11px] text-[#8a8886]">{dt.range}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Number of Factors Dropdown */}
            <Field label={{ children: <span className="text-xs font-semibold text-[#323130]">Number of Factors:</span> }}>
              <select
                value={numFactors}
                onChange={(e) => setNumFactors(Number(e.target.value))}
                className="w-full px-2.5 py-1.5 text-xs bg-white border border-[#d2d0ce] focus:border-[#008450] rounded-md outline-none text-[#201f1e]"
              >
                {Array.from({ length: 14 }, (_, i) => i + 2).map((k) => (
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
                  {selectedRuns} Runs
                </span>
              </div>
              <p className="text-[11.5px] leading-relaxed">
                Factors: <strong>{numFactors}</strong> ({factorNames.slice(0, numFactors).join(', ')}) • Replicates: <strong>{numReplicates}</strong> • Center Points: <strong>{centerPoints}</strong> • Blocks: <strong>{numBlocks}</strong>
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

      {/* 2. SUB-MODAL: [Designs...] Catalog & Replication */}
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
                  Available Factorial Designs ({numFactors} Factors)
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
                      <TableHeaderCell style={{ fontWeight: 700 }}>Runs</TableHeaderCell>
                      <TableHeaderCell style={{ fontWeight: 700 }}>Fraction</TableHeaderCell>
                      <TableHeaderCell style={{ fontWeight: 700 }}>Resolution</TableHeaderCell>
                      <TableHeaderCell style={{ fontWeight: 700, textAlign: 'center' }}>Select</TableHeaderCell>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {availableOptionsForK.map((opt) => {
                      const isSelected = selectedRuns === opt.runs;
                      return (
                        <TableRow
                          key={opt.runs}
                          onClick={() => setSelectedRuns(opt.runs)}
                          className={`cursor-pointer transition-colors ${
                            isSelected ? 'bg-[#e6faf0]' : 'hover:bg-[#f5f5f5]'
                          }`}
                        >
                          <TableCell style={{ fontWeight: 600, color: '#008450' }}>
                            {opt.runs} Runs
                          </TableCell>
                          <TableCell>{opt.fraction}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              {getResBadge(opt.resCode)}
                              <span className="text-xs text-[#605e5c]">{opt.resolution}</span>
                            </div>
                          </TableCell>
                          <TableCell style={{ textAlign: 'center' }}>
                            <input
                              type="radio"
                              name="selected_runs_radio"
                              checked={isSelected}
                              onChange={() => setSelectedRuns(opt.runs)}
                              className="text-[#008450] cursor-pointer"
                            />
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>

              {/* Design Parameters Grid */}
              <div className="grid grid-cols-3 gap-3 pt-2">
                <Field label={{ children: <span className="text-xs font-semibold">Center points per block:</span> }}>
                  <Input
                    size="small"
                    type="number"
                    min={0}
                    max={12}
                    value={String(centerPoints)}
                    onChange={(_, data) => setCenterPoints(Number(data.value) || 0)}
                  />
                </Field>
                <Field label={{ children: <span className="text-xs font-semibold">Number of Replicates:</span> }}>
                  <Input
                    size="small"
                    type="number"
                    min={1}
                    max={10}
                    value={String(numReplicates)}
                    onChange={(_, data) => setNumReplicates(Number(data.value) || 1)}
                  />
                </Field>
                <Field label={{ children: <span className="text-xs font-semibold">Number of Blocks:</span> }}>
                  <select
                    value={numBlocks}
                    onChange={(e) => setNumBlocks(Number(e.target.value))}
                    className="w-full px-2 py-1 text-xs bg-white border border-[#d2d0ce] focus:border-[#008450] rounded-md outline-none"
                  >
                    <option value={1}>1 Block (Unblocked)</option>
                    <option value={2}>2 Blocks</option>
                    <option value={4}>4 Blocks</option>
                  </select>
                </Field>
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

      {/* 3. SUB-MODAL: [Factors...] Level Configuration */}
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
                <h3 className="text-sm font-bold text-[#201f1e]">Factors and Level Settings</h3>
              </div>
              <Button
                appearance="subtle"
                size="small"
                icon={<DismissRegular />}
                onClick={() => setShowFactorsModal(false)}
              />
            </div>

            <div className="p-5 space-y-3 overflow-y-auto max-h-[60vh]">
              <div className="border border-[#e0e0e0] rounded-lg overflow-hidden">
                <Table size="small">
                  <TableHeader>
                    <TableRow className="bg-[#f0f0f0]">
                      <TableHeaderCell style={{ width: '60px', fontWeight: 700 }}>Factor</TableHeaderCell>
                      <TableHeaderCell style={{ fontWeight: 700 }}>Name</TableHeaderCell>
                      <TableHeaderCell style={{ width: '110px', fontWeight: 700 }}>Role</TableHeaderCell>
                      <TableHeaderCell style={{ width: '110px', fontWeight: 700 }}>Low (-1)</TableHeaderCell>
                      <TableHeaderCell style={{ width: '110px', fontWeight: 700 }}>High (+1)</TableHeaderCell>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Array.from({ length: numFactors }, (_, idx) => (
                      <TableRow key={idx}>
                        <TableCell style={{ fontWeight: 600, color: '#008450' }}>
                          {String.fromCharCode(65 + idx)}
                        </TableCell>
                        <TableCell>
                          <Input
                            size="small"
                            value={factorNames[idx] || ''}
                            onChange={(_, data) => {
                              const updated = [...factorNames];
                              updated[idx] = data.value;
                              setFactorNames(updated);
                            }}
                            className="w-full"
                          />
                        </TableCell>
                        <TableCell>
                          <select
                            value={factorTypes[idx] || 'Numeric'}
                            onChange={(e) => {
                              const updated = [...factorTypes];
                              updated[idx] = e.target.value;
                              setFactorTypes(updated);
                            }}
                            className="w-full px-2 py-1 text-xs border border-[#d2d0ce] rounded outline-none"
                          >
                            <option value="Numeric">Numeric</option>
                            <option value="Text">Text</option>
                          </select>
                        </TableCell>
                        <TableCell>
                          <Input
                            size="small"
                            value={factorLows[idx] || ''}
                            onChange={(_, data) => {
                              const updated = [...factorLows];
                              updated[idx] = data.value;
                              setFactorLows(updated);
                            }}
                            className="w-full"
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            size="small"
                            value={factorHighs[idx] || ''}
                            onChange={(_, data) => {
                              const updated = [...factorHighs];
                              updated[idx] = data.value;
                              setFactorHighs(updated);
                            }}
                            className="w-full"
                          />
                        </TableCell>
                      </TableRow>
                    ))}
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

      {/* 4. SUB-MODAL: [Options...] */}
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
                <h3 className="text-sm font-bold text-[#201f1e]">Factorial Design Options</h3>
              </div>
              <Button
                appearance="subtle"
                size="small"
                icon={<DismissRegular />}
                onClick={() => setShowOptionsModal(false)}
              />
            </div>

            <div className="p-5 space-y-4 text-xs">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={randomizeRuns}
                  onChange={(e) => setRandomizeRuns(e.target.checked)}
                  className="w-4 h-4 text-[#008450] border-[#d2d0ce] rounded cursor-pointer"
                />
                <span className="font-semibold text-[#323130]">Randomize run order</span>
              </label>

              <Field label={{ children: <span className="text-xs font-semibold">Base for random number generator (Seed):</span> }}>
                <Input
                  size="small"
                  type="number"
                  placeholder="Optional numeric seed (e.g. 12345)"
                  value={randomSeed}
                  onChange={(_, data) => setRandomSeed(data.value)}
                  className="w-full"
                />
              </Field>

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

      {/* 5. SUB-MODAL: [Results...] */}
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
                <div>Design: 2-Level Factorial</div>
                <div>Factors: {numFactors} ({factorNames.slice(0, numFactors).join(', ')})</div>
                <div>Base Runs: {selectedRuns}</div>
                <div>Total Runs: {selectedRuns * numReplicates + centerPoints * numBlocks}</div>
                <div>Replicates: {numReplicates}</div>
                <div>Center Points: {centerPoints * numBlocks}</div>
                <div>Blocks: {numBlocks}</div>
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

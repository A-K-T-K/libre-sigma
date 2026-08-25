import React, { useEffect, useState } from 'react';
import {
  Button,
  Input,
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

export const RsmCreateModal: React.FC = () => {
  const { activePluginId, closeDialog, runCompute, isComputing, computeError } = usePluginStore();

  const [designType, setDesignType] = useState<string>('ccd');
  const [numFactors, setNumFactors] = useState<number>(3);
  const [ccdSubtype, setCcdSubtype] = useState<string>('full');
  const [alphaChoice, setAlphaChoice] = useState<string>('rotatable');
  const [customAlpha, setCustomAlpha] = useState<string>('1.682');
  const [cubeCenterPoints, setCubeCenterPoints] = useState<number>(4);
  const [axialCenterPoints, setAxialCenterPoints] = useState<number>(2);
  const [bbdCenterPoints, setBbdCenterPoints] = useState<number>(3);
  const [numReplicates, setNumReplicates] = useState<number>(1);
  const [numBlocks, setNumBlocks] = useState<number>(1);
  const [randomizeRuns, setRandomizeRuns] = useState<boolean>(true);
  const [randomSeed, setRandomSeed] = useState<string>('');
  const [worksheetName, setWorksheetName] = useState<string>('RSM Design');

  // Factor Settings
  const [factorNames, setFactorNames] = useState<string[]>(['A', 'B', 'C']);
  const [factorLows, setFactorLows] = useState<string[]>(['-1', '-1', '-1']);
  const [factorHighs, setFactorHighs] = useState<string[]>(['1', '1', '1']);

  // Sub-modals state
  const [showDesignsModal, setShowDesignsModal] = useState<boolean>(false);
  const [showFactorsModal, setShowFactorsModal] = useState<boolean>(false);
  const [showOptionsModal, setShowOptionsModal] = useState<boolean>(false);

  const isOpen = activePluginId === 'doe_create_rsm';

  // Compute calculated Alpha value for display and level table
  const getComputedAlpha = (): number => {
    if (designType === 'bbd') return 1.0;
    if (alphaChoice === 'face_centered') return 1.0;
    if (alphaChoice === 'spherical') return Math.sqrt(numFactors);
    if (alphaChoice === 'custom') return Number(customAlpha) || 1.682;
    const nCube = ccdSubtype === 'fractional' && numFactors >= 5 ? Math.pow(2, numFactors - 1) : Math.pow(2, numFactors);
    if (alphaChoice === 'orthogonal') {
      return Math.sqrt((numFactors * (nCube + 2 * cubeCenterPoints)) / (2 * nCube));
    }
    return Math.pow(nCube, 0.25); // Rotatable
  };

  const alphaVal = getComputedAlpha();

  // Synchronize factor counts
  useEffect(() => {
    const minK = designType === 'bbd' ? 3 : 2;
    const k = Math.max(minK, numFactors);
    setNumFactors(k);
    setFactorNames(Array.from({ length: k }, (_, i) => String.fromCharCode(65 + i)));
    setFactorLows(Array.from({ length: k }, () => '-1'));
    setFactorHighs(Array.from({ length: k }, () => '1'));
  }, [designType, numFactors]);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    const payload = {
      design_type: designType,
      num_factors: numFactors,
      ccd_subtype: ccdSubtype,
      alpha_choice: alphaChoice,
      custom_alpha: alphaChoice === 'custom' ? Number(customAlpha) : null,
      cube_center_points: Number(cubeCenterPoints) || 0,
      axial_center_points: Number(axialCenterPoints) || 0,
      bbd_center_points: Number(bbdCenterPoints) || 3,
      num_replicates: Number(numReplicates) || 1,
      num_blocks: Number(numBlocks) || 1,
      factor_names_str: factorNames.slice(0, numFactors).join(', '),
      factor_lows_str: factorLows.slice(0, numFactors).join(', '),
      factor_highs_str: factorHighs.slice(0, numFactors).join(', '),
      randomize_runs: randomizeRuns,
      random_seed: randomSeed.trim() ? Number(randomSeed) : null,
      worksheet_name: worksheetName.trim() || 'RSM Design',
    };

    const success = await runCompute('doe_create_rsm', payload);
    if (success) {
      closeDialog();
    }
  };

  return (
    <>
      {/* 1. PRIMARY MODAL: Create Response Surface Design */}
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
                Create Response Surface Design
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
                Response Surface Design Type:
              </label>
              <div className="space-y-2 pl-1">
                <label className="flex items-start space-x-2.5 cursor-pointer py-0.5 hover:text-[#008450] text-xs text-[#323130]">
                  <input
                    type="radio"
                    name="rsm_design_type"
                    checked={designType === 'ccd'}
                    onChange={() => setDesignType('ccd')}
                    className="text-[#008450] mt-0.5 cursor-pointer"
                  />
                  <div>
                    <span className="font-semibold">Central Composite Design (CCD)</span>
                    <p className="text-[11px] text-[#605e5c]">
                      Full or fractional factorial core with axial points at distance α (2 to 10 factors).
                    </p>
                  </div>
                </label>

                <label className="flex items-start space-x-2.5 cursor-pointer py-0.5 hover:text-[#008450] text-xs text-[#323130]">
                  <input
                    type="radio"
                    name="rsm_design_type"
                    checked={designType === 'bbd'}
                    onChange={() => setDesignType('bbd')}
                    className="text-[#008450] mt-0.5 cursor-pointer"
                  />
                  <div>
                    <span className="font-semibold">Box-Behnken Design (BBD)</span>
                    <p className="text-[11px] text-[#605e5c]">
                      Spherical design without extreme corner points; requires only 3 levels: -1, 0, +1 (3 to 10 factors).
                    </p>
                  </div>
                </label>
              </div>
            </div>

            {/* Number of Continuous Factors Dropdown */}
            <Field label={{ children: <span className="text-xs font-semibold text-[#323130]">Number of Continuous Factors:</span> }}>
              <select
                value={numFactors}
                onChange={(e) => setNumFactors(Number(e.target.value))}
                className="w-full px-2.5 py-1.5 text-xs bg-white border border-[#d2d0ce] focus:border-[#008450] rounded-md outline-none text-[#201f1e]"
              >
                {Array.from({ length: 9 }, (_, i) => i + (designType === 'bbd' ? 3 : 2)).map((k) => (
                  <option key={k} value={k}>
                    {k} Continuous Factors ({String.fromCharCode(65)} through {String.fromCharCode(65 + k - 1)})
                  </option>
                ))}
              </select>
            </Field>

            {/* Summary Box */}
            <div className="p-3 bg-[#e6faf0]/70 border border-[#bbf2d6] rounded-md text-xs text-[#004d2c] space-y-1">
              <div className="font-semibold flex items-center justify-between">
                <span>Selected Configuration:</span>
                <span className="bg-[#008450] text-white px-2 py-0.5 rounded text-[11px] font-semibold">
                  {designType.toUpperCase()} (k = {numFactors})
                </span>
              </div>
              <p className="text-[11.5px] leading-relaxed">
                {designType === 'ccd'
                  ? `Axial Distance α = ${alphaVal.toFixed(3)} (${alphaChoice}) • Center Points: ${cubeCenterPoints + axialCenterPoints}`
                  : `Box-Behnken (3 Levels) • Center Points: ${bbdCenterPoints}`}
              </p>
            </div>

            {/* Sub-modal Action Buttons */}
            <div className="grid grid-cols-3 gap-2.5 pt-2 border-t border-[#edebe9]">
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

      {/* 2. SUB-MODAL: [Designs...] CCD/BBD Axial & Center Point Configuration */}
      {showDesignsModal && (
        <div
          className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 backdrop-blur-[1px] p-4 select-none animate-in fade-in duration-100"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowDesignsModal(false);
          }}
        >
          <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-full max-w-xl overflow-hidden flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-100">
            <div className="flex items-center justify-between px-5 py-3.5 bg-[#f8f9fa] border-b border-[#e0e0e0]">
              <div className="flex items-center gap-2">
                <TableRegular className="text-[#008450]" />
                <h3 className="text-sm font-bold text-[#201f1e]">
                  {designType === 'ccd' ? 'Central Composite Design Specifications' : 'Box-Behnken Design Specifications'}
                </h3>
              </div>
              <Button
                appearance="subtle"
                size="small"
                icon={<DismissRegular />}
                onClick={() => setShowDesignsModal(false)}
              />
            </div>

            <div className="p-5 space-y-4 overflow-y-auto max-h-[60vh] text-xs">
              {designType === 'ccd' ? (
                <>
                  {/* CCD Subtypes */}
                  <div className="space-y-2">
                    <label className="font-semibold text-[#201f1e] block">Factorial Core:</label>
                    <div className="flex gap-4">
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                          type="radio"
                          name="ccd_subtype"
                          checked={ccdSubtype === 'full'}
                          onChange={() => setCcdSubtype('full')}
                          className="text-[#008450]"
                        />
                        <span>Full Factorial Core (2^{numFactors} = {Math.pow(2, numFactors)} points)</span>
                      </label>
                      {numFactors >= 5 && (
                        <label className="flex items-center gap-1.5 cursor-pointer">
                          <input
                            type="radio"
                            name="ccd_subtype"
                            checked={ccdSubtype === 'fractional'}
                            onChange={() => setCcdSubtype('fractional')}
                            className="text-[#008450]"
                          />
                          <span>Small / Half-Fraction Core (2^{numFactors - 1} points)</span>
                        </label>
                      )}
                    </div>
                  </div>

                  {/* Alpha Position */}
                  <div className="space-y-2 pt-2 border-t border-[#edebe9]">
                    <label className="font-semibold text-[#201f1e] block">
                      Axial / Star Point Position (Alpha α):
                    </label>
                    <div className="space-y-1.5 pl-1">
                      {[
                        { id: 'rotatable', label: 'Rotatable', desc: 'Equal prediction variance at all points equidistant from center' },
                        { id: 'spherical', label: 'Spherical', desc: 'All factorial and axial points lie on a sphere of radius sqrt(k)' },
                        { id: 'face_centered', label: 'Face-Centered (CCF)', desc: 'Axial points on cube faces (alpha = 1.0, requires only 3 levels)' },
                        { id: 'orthogonal', label: 'Orthogonal Blocking', desc: 'Blocks orthogonal to main and quadratic terms' },
                        { id: 'custom', label: 'Custom Value', desc: 'Specify exact numeric alpha' },
                      ].map((item) => (
                        <label key={item.id} className="flex items-start gap-2 cursor-pointer">
                          <input
                            type="radio"
                            name="alpha_choice"
                            checked={alphaChoice === item.id}
                            onChange={() => setAlphaChoice(item.id)}
                            className="text-[#008450] mt-0.5"
                          />
                          <div>
                            <span className="font-medium">{item.label}</span>
                            <span className="text-[11px] text-[#8a8886] ml-2">({item.desc})</span>
                          </div>
                        </label>
                      ))}
                    </div>

                    {alphaChoice === 'custom' && (
                      <div className="pl-6 pt-1">
                        <Field label={{ children: <span className="text-xs">Custom Alpha Value:</span> }}>
                          <Input
                            size="small"
                            type="number"
                            step="0.001"
                            value={customAlpha}
                            onChange={(_, data) => setCustomAlpha(data.value)}
                          />
                        </Field>
                      </div>
                    )}
                  </div>

                  {/* Center Points */}
                  <div className="grid grid-cols-2 gap-3 pt-2 border-t border-[#edebe9]">
                    <Field label={{ children: <span className="text-xs font-semibold">Center points in Cube block:</span> }}>
                      <Input
                        size="small"
                        type="number"
                        min={0}
                        max={12}
                        value={String(cubeCenterPoints)}
                        onChange={(_, data) => setCubeCenterPoints(Number(data.value) || 0)}
                      />
                    </Field>
                    <Field label={{ children: <span className="text-xs font-semibold">Center points in Axial block:</span> }}>
                      <Input
                        size="small"
                        type="number"
                        min={0}
                        max={12}
                        value={String(axialCenterPoints)}
                        onChange={(_, data) => setAxialCenterPoints(Number(data.value) || 0)}
                      />
                    </Field>
                  </div>
                </>
              ) : (
                /* BBD Options */
                <div className="space-y-3">
                  <Field label={{ children: <span className="text-xs font-semibold">Number of Center Points:</span> }}>
                    <Input
                      size="small"
                      type="number"
                      min={1}
                      max={12}
                      value={String(bbdCenterPoints)}
                      onChange={(_, data) => setBbdCenterPoints(Number(data.value) || 3)}
                    />
                  </Field>
                </div>
              )}
            </div>

            <div className="px-5 py-3 bg-[#f8f9fa] border-t border-[#e0e0e0] flex items-center justify-end">
              <Button appearance="primary" size="medium" onClick={() => setShowDesignsModal(false)}>
                OK
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 3. SUB-MODAL: [Factors...] Level & Axial Ranges */}
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
                <h3 className="text-sm font-bold text-[#201f1e]">Factors, Operating Ranges & Axial Points</h3>
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
                      <TableHeaderCell style={{ width: '50px', fontWeight: 700 }}>Factor</TableHeaderCell>
                      <TableHeaderCell style={{ fontWeight: 700 }}>Name</TableHeaderCell>
                      <TableHeaderCell style={{ width: '90px', fontWeight: 700 }}>Low (-1)</TableHeaderCell>
                      <TableHeaderCell style={{ width: '90px', fontWeight: 700 }}>High (+1)</TableHeaderCell>
                      <TableHeaderCell style={{ width: '100px', fontWeight: 700 }}>Axial Low (-α)</TableHeaderCell>
                      <TableHeaderCell style={{ width: '100px', fontWeight: 700 }}>Axial High (+α)</TableHeaderCell>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Array.from({ length: numFactors }, (_, idx) => {
                      const lVal = Number(factorLows[idx]) || -1;
                      const hVal = Number(factorHighs[idx]) || 1;
                      const mid = (lVal + hVal) / 2.0;
                      const half = (hVal - lVal) / 2.0;
                      const axLow = (mid - alphaVal * half).toFixed(2);
                      const axHigh = (mid + alphaVal * half).toFixed(2);

                      return (
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
                          <TableCell style={{ color: '#605e5c' }}>
                            {axLow}
                          </TableCell>
                          <TableCell style={{ color: '#605e5c' }}>
                            {axHigh}
                          </TableCell>
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
                <h3 className="text-sm font-bold text-[#201f1e]">RSM Design Options</h3>
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
                  placeholder="Optional numeric seed"
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
    </>
  );
};

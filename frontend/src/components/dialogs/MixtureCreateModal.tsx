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
  TabList,
  Tab,
} from '@fluentui/react-components';
import {
  SparkleRegular,
  DismissRegular,
  TableRegular,
  OptionsRegular,
  DocumentBulletListRegular,
  InfoRegular,
  LayerDiagonalRegular,
} from '@fluentui/react-icons';
import { usePluginStore } from '../../store/usePluginStore';

export const MixtureCreateModal: React.FC = () => {
  const { activePluginId, closeDialog, runCompute, isComputing, computeError } = usePluginStore();

  const [designType, setDesignType] = useState<string>('simplex_centroid');
  const [numComponents, setNumComponents] = useState<number>(3);
  const [mixtureTotal, setMixtureTotal] = useState<number>(1.0);
  const [latticeDegree, setLatticeDegree] = useState<number>(2);
  const [augmentInterior, setAugmentInterior] = useState<boolean>(true);
  const [augmentAxial, setAugmentAxial] = useState<boolean>(false);
  const [numReplicates, setNumReplicates] = useState<number>(1);
  const [randomizeRuns, setRandomizeRuns] = useState<boolean>(true);
  const [randomSeed, setRandomSeed] = useState<string>('');
  const [worksheetName, setWorksheetName] = useState<string>('Mixture Design');

  // Component Settings
  const [compNames, setCompNames] = useState<string[]>(['Comp_A', 'Comp_B', 'Comp_C']);
  const [compRoles, setCompRoles] = useState<string[]>(['Proportion', 'Proportion', 'Proportion']);
  const [compLows, setCompLows] = useState<string[]>(['0', '0', '0']);
  const [compHighs, setCompHighs] = useState<string[]>(['1', '1', '1']);

  // Process Variables (crossing)
  const [processVars, setProcessVars] = useState<string>('');

  // Sub-modals state
  const [showComponentsModal, setShowComponentsModal] = useState<boolean>(false);
  const [componentsTab, setComponentsTab] = useState<'bounds' | 'constraints'>('bounds');
  const [showProcessModal, setShowProcessModal] = useState<boolean>(false);
  const [showOptionsModal, setShowOptionsModal] = useState<boolean>(false);

  const isOpen = activePluginId === 'doe_create_mixture';

  // Synchronize component arrays
  useEffect(() => {
    const q = Math.max(2, Math.min(12, numComponents));
    setNumComponents(q);
    setCompNames(Array.from({ length: q }, (_, i) => `Comp_${String.fromCharCode(65 + i)}`));
    setCompRoles(Array.from({ length: q }, () => 'Proportion'));
    setCompLows(Array.from({ length: q }, () => '0'));
    setCompHighs(Array.from({ length: q }, () => String(mixtureTotal)));
  }, [numComponents, mixtureTotal]);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    const payload = {
      design_type: designType,
      num_components: numComponents,
      mixture_total: Number(mixtureTotal) || 1.0,
      lattice_degree: Number(latticeDegree) || 2,
      augment_interior: augmentInterior,
      augment_axial: augmentAxial,
      num_replicates: Number(numReplicates) || 1,
      component_names_str: compNames.slice(0, numComponents).join(', '),
      lower_bounds_str: compLows.slice(0, numComponents).join(', '),
      upper_bounds_str: compHighs.slice(0, numComponents).join(', '),
      process_variables_str: processVars.trim(),
      randomize_runs: randomizeRuns,
      random_seed: randomSeed.trim() ? Number(randomSeed) : null,
      worksheet_name: worksheetName.trim() || 'Mixture Design',
    };

    const success = await runCompute('doe_create_mixture', payload);
    if (success) {
      closeDialog();
    }
  };

  return (
    <>
      {/* 1. PRIMARY MODAL: Create Mixture Design */}
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
                Create Mixture Design
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
                Mixture Design Type:
              </label>
              <div className="space-y-2 pl-1">
                <label className="flex items-start space-x-2.5 cursor-pointer py-0.5 hover:text-[#008450] text-xs text-[#323130]">
                  <input
                    type="radio"
                    name="mixture_design_type"
                    checked={designType === 'simplex_centroid'}
                    onChange={() => setDesignType('simplex_centroid')}
                    className="text-[#008450] mt-0.5 cursor-pointer"
                  />
                  <div>
                    <span className="font-semibold">Simplex Centroid Design</span>
                    <p className="text-[11px] text-[#605e5c]">
                      Generates pure components, binary blends, ternary blends, up to overall centroid.
                    </p>
                  </div>
                </label>

                <label className="flex items-start space-x-2.5 cursor-pointer py-0.5 hover:text-[#008450] text-xs text-[#323130]">
                  <input
                    type="radio"
                    name="mixture_design_type"
                    checked={designType === 'simplex_lattice'}
                    onChange={() => setDesignType('simplex_lattice')}
                    className="text-[#008450] mt-0.5 cursor-pointer"
                  />
                  <div>
                    <span className="font-semibold">Simplex Lattice Design</span>
                    <p className="text-[11px] text-[#605e5c]">
                      Generates triangular lattice points of specified polynomial degree m.
                    </p>
                  </div>
                </label>

                <label className="flex items-start space-x-2.5 cursor-pointer py-0.5 hover:text-[#008450] text-xs text-[#323130]">
                  <input
                    type="radio"
                    name="mixture_design_type"
                    checked={designType === 'extreme_vertices'}
                    onChange={() => setDesignType('extreme_vertices')}
                    className="text-[#008450] mt-0.5 cursor-pointer"
                  />
                  <div>
                    <span className="font-semibold">Extreme Vertices / Constrained Mixture</span>
                    <p className="text-[11px] text-[#605e5c]">
                      For formulations with lower/upper bound component constraints (L_i ≤ x_i ≤ U_i).
                    </p>
                  </div>
                </label>
              </div>
            </div>

            {/* Number of Components & Mixture Total */}
            <div className="grid grid-cols-2 gap-3">
              <Field label={{ children: <span className="text-xs font-semibold text-[#323130]">Number of Components:</span> }}>
                <select
                  value={numComponents}
                  onChange={(e) => setNumComponents(Number(e.target.value))}
                  className="w-full px-2.5 py-1.5 text-xs bg-white border border-[#d2d0ce] focus:border-[#008450] rounded-md outline-none text-[#201f1e]"
                >
                  {Array.from({ length: 11 }, (_, i) => i + 2).map((q) => (
                    <option key={q} value={q}>
                      {q} Components (Comp_A ... Comp_{String.fromCharCode(65 + q - 1)})
                    </option>
                  ))}
                </select>
              </Field>

              <Field label={{ children: <span className="text-xs font-semibold text-[#323130]">Mixture Total:</span> }}>
                <select
                  value={mixtureTotal}
                  onChange={(e) => setMixtureTotal(Number(e.target.value))}
                  className="w-full px-2.5 py-1.5 text-xs bg-white border border-[#d2d0ce] focus:border-[#008450] rounded-md outline-none text-[#201f1e]"
                >
                  <option value={1.0}>1.0 (Proportions)</option>
                  <option value={100.0}>100.0 (Percentages %)</option>
                </select>
              </Field>
            </div>

            {/* Lattice specific options */}
            {designType === 'simplex_lattice' && (
              <Field label={{ children: <span className="text-xs font-semibold text-[#323130]">Lattice Degree (m):</span> }}>
                <select
                  value={latticeDegree}
                  onChange={(e) => setLatticeDegree(Number(e.target.value))}
                  className="w-full px-2.5 py-1.5 text-xs bg-white border border-[#d2d0ce] focus:border-[#008450] rounded-md outline-none text-[#201f1e]"
                >
                  <option value={1}>Degree 1 (Linear, pure components)</option>
                  <option value={2}>Degree 2 (Quadratic, binary blends)</option>
                  <option value={3}>Degree 3 (Special Cubic, ternary blends)</option>
                  <option value={4}>Degree 4 (Quartic blends)</option>
                </select>
              </Field>
            )}

            {/* Summary Box */}
            <div className="p-3 bg-[#e6faf0]/70 border border-[#bbf2d6] rounded-md text-xs text-[#004d2c] space-y-1">
              <div className="font-semibold flex items-center justify-between">
                <span>Selected Mixture Setup:</span>
                <span className="bg-[#008450] text-white px-2 py-0.5 rounded text-[11px] font-semibold">
                  q = {numComponents} Components (Total = {mixtureTotal})
                </span>
              </div>
              <p className="text-[11.5px] leading-relaxed">
                Components: <strong>{compNames.slice(0, numComponents).join(', ')}</strong> • Replicates: <strong>{numReplicates}</strong>
                {processVars ? ` • Process crossed: ${processVars}` : ''}
              </p>
            </div>

            {/* Sub-modal Action Buttons */}
            <div className="grid grid-cols-3 gap-2.5 pt-2 border-t border-[#edebe9]">
              <Button
                appearance="secondary"
                size="small"
                icon={<DocumentBulletListRegular className="text-[#008450]" />}
                onClick={() => setShowComponentsModal(true)}
              >
                Components...
              </Button>
              <Button
                appearance="secondary"
                size="small"
                icon={<LayerDiagonalRegular className="text-[#008450]" />}
                onClick={() => setShowProcessModal(true)}
              >
                Process Vars...
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

      {/* 2. SUB-MODAL: [Components...] Bounds & Constraints */}
      {showComponentsModal && (
        <div
          className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 backdrop-blur-[1px] p-4 select-none animate-in fade-in duration-100"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowComponentsModal(false);
          }}
        >
          <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-full max-w-2xl overflow-hidden flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-100">
            <div className="flex items-center justify-between px-5 py-3.5 bg-[#f8f9fa] border-b border-[#e0e0e0]">
              <div className="flex items-center gap-2">
                <DocumentBulletListRegular className="text-[#008450]" />
                <h3 className="text-sm font-bold text-[#201f1e]">Components & Formulation Bounds</h3>
              </div>
              <Button
                appearance="subtle"
                size="small"
                icon={<DismissRegular />}
                onClick={() => setShowComponentsModal(false)}
              />
            </div>

            <div className="p-5 space-y-3 overflow-y-auto max-h-[60vh]">
              <div className="border border-[#e0e0e0] rounded-lg overflow-hidden">
                <Table size="small">
                  <TableHeader>
                    <TableRow className="bg-[#f0f0f0]">
                      <TableHeaderCell style={{ width: '50px', fontWeight: 700 }}>Index</TableHeaderCell>
                      <TableHeaderCell style={{ fontWeight: 700 }}>Component Name</TableHeaderCell>
                      <TableHeaderCell style={{ width: '100px', fontWeight: 700 }}>Role</TableHeaderCell>
                      <TableHeaderCell style={{ width: '100px', fontWeight: 700 }}>Lower Bound</TableHeaderCell>
                      <TableHeaderCell style={{ width: '100px', fontWeight: 700 }}>Upper Bound</TableHeaderCell>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Array.from({ length: numComponents }, (_, idx) => (
                      <TableRow key={idx}>
                        <TableCell style={{ fontWeight: 600, color: '#008450' }}>
                          X{idx + 1}
                        </TableCell>
                        <TableCell>
                          <Input
                            size="small"
                            value={compNames[idx] || ''}
                            onChange={(_, data) => {
                              const updated = [...compNames];
                              updated[idx] = data.value;
                              setCompNames(updated);
                            }}
                            className="w-full"
                          />
                        </TableCell>
                        <TableCell>
                          <select
                            value={compRoles[idx] || 'Proportion'}
                            onChange={(e) => {
                              const updated = [...compRoles];
                              updated[idx] = e.target.value;
                              setCompRoles(updated);
                            }}
                            className="w-full px-2 py-1 text-xs border border-[#d2d0ce] rounded outline-none"
                          >
                            <option value="Proportion">Proportion</option>
                            <option value="Amount">Amount</option>
                          </select>
                        </TableCell>
                        <TableCell>
                          <Input
                            size="small"
                            value={compLows[idx] || ''}
                            onChange={(_, data) => {
                              const updated = [...compLows];
                              updated[idx] = data.value;
                              setCompLows(updated);
                            }}
                            className="w-full"
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            size="small"
                            value={compHighs[idx] || ''}
                            onChange={(_, data) => {
                              const updated = [...compHighs];
                              updated[idx] = data.value;
                              setCompHighs(updated);
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
              <Button appearance="primary" size="medium" onClick={() => setShowComponentsModal(false)}>
                OK
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 3. SUB-MODAL: [Process Variables...] */}
      {showProcessModal && (
        <div
          className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 backdrop-blur-[1px] p-4 select-none animate-in fade-in duration-100"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowProcessModal(false);
          }}
        >
          <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-full max-w-md overflow-hidden flex flex-col animate-in zoom-in-95 duration-100">
            <div className="flex items-center justify-between px-5 py-3.5 bg-[#f8f9fa] border-b border-[#e0e0e0]">
              <div className="flex items-center gap-2">
                <LayerDiagonalRegular className="text-[#008450]" />
                <h3 className="text-sm font-bold text-[#201f1e]">Process Variables Crossing</h3>
              </div>
              <Button
                appearance="subtle"
                size="small"
                icon={<DismissRegular />}
                onClick={() => setShowProcessModal(false)}
              />
            </div>

            <div className="p-5 space-y-3 text-xs">
              <p className="text-[#605e5c] leading-relaxed">
                Optionally cross the mixture formulation blends with 2-level factorial process factors (e.g. Temperature, Mixer Speed).
              </p>
              <Field label={{ children: <span className="text-xs font-semibold">Process Variables (comma-separated):</span> }}>
                <Input
                  size="small"
                  placeholder="e.g. Temperature, Speed (leave blank if none)"
                  value={processVars}
                  onChange={(_, data) => setProcessVars(data.value)}
                  className="w-full"
                />
              </Field>
            </div>

            <div className="px-5 py-3 bg-[#f8f9fa] border-t border-[#e0e0e0] flex items-center justify-end">
              <Button appearance="primary" size="medium" onClick={() => setShowProcessModal(false)}>
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
                <h3 className="text-sm font-bold text-[#201f1e]">Mixture Design Options</h3>
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

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={augmentInterior}
                  onChange={(e) => setAugmentInterior(e.target.checked)}
                  className="w-4 h-4 text-[#008450] border-[#d2d0ce] rounded cursor-pointer"
                />
                <span className="font-semibold text-[#323130]">Augment with interior centroid points</span>
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

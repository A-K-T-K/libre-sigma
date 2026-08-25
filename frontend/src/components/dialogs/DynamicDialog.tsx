import React, { useEffect, useState } from 'react';
import {
  Button,
  Input,
  Field,
  Spinner,
} from '@fluentui/react-components';
import {
  DismissRegular,
  ArrowRightRegular,
  InfoRegular,
  DismissCircleRegular,
  TableRegular,
  SparkleRegular,
  QuestionCircleRegular,
  SearchRegular,
  SettingsRegular,
  OptionsRegular,
  StorageRegular,
  DataTrendingRegular,
} from '@fluentui/react-icons';
import katex from 'katex';
import { usePluginStore } from '../../store/usePluginStore';
import { useWorksheetStore } from '../../store/useWorksheetStore';
import { getMenuOrPluginIcon } from '../../utils/menuIcons';


const MathFormulaCard: React.FC<{ snType: string; targetVal?: any }> = ({ snType, targetVal }) => {
  let mathStr = '';
  let goalStr = '';

  if (snType === 'larger') {
    mathStr = '\\eta = -10 \\cdot \\log_{10}\\left(\\frac{1}{n} \\sum_{i=1}^{n} \\frac{1}{y_i^2}\\right)';
    goalStr = 'Maximizes the response characteristic.';
  } else if (snType === 'smaller') {
    mathStr = '\\eta = -10 \\cdot \\log_{10}\\left(\\frac{1}{n} \\sum_{i=1}^{n} y_i^2\\right)';
    goalStr = 'Minimizes the response characteristic towards zero.';
  } else {
    const hasTarget = targetVal !== undefined && targetVal !== '' && !isNaN(Number(targetVal));
    const targetLabel = hasTarget ? `(y_i - ${targetVal})^2` : '(y_i - T)^2';
    mathStr = `\\eta = -10 \\cdot \\log_{10}\\left(\\frac{1}{n} \\sum_{i=1}^{n} ${targetLabel}\\right)`;
    goalStr = hasTarget
      ? `Targets nominal specification T = ${targetVal} while minimizing process variance.`
      : 'Targets nominal specification T while minimizing process variance.';
  }

  let renderedHtml = '';
  try {
    renderedHtml = katex.renderToString(mathStr, {
      throwOnError: false,
      displayMode: true,
    });
  } catch {
    renderedHtml = `<code>${mathStr}</code>`;
  }

  return (
    <div className="mt-2 p-3 bg-[#e6faf0]/60 border border-[#bbf2d6] rounded-lg text-xs space-y-1.5 animate-in fade-in duration-100">
      <div className="flex items-center justify-between text-[11px] font-semibold text-[#008450]">
        <span className="flex items-center gap-1">
          <SparkleRegular className="w-3.5 h-3.5" />
          <span>S/N Mathematical Formulation</span>
        </span>
        <span className="text-[10px] bg-[#008450] text-white px-1.5 py-0.2 rounded font-medium">
          {snType === 'larger' ? 'Larger is Better' : snType === 'smaller' ? 'Smaller is Better' : 'Nominal is Best'}
        </span>
      </div>
      <div
        className="py-1 text-center text-[#004d2c] overflow-x-auto text-sm"
        dangerouslySetInnerHTML={{ __html: renderedHtml }}
      />
      <div className="text-[11px] text-[#2e5b44] font-medium text-center">
        {goalStr}
      </div>
    </div>
  );
};

export const DynamicDialog: React.FC = () => {
  const { activePluginId, getPlugin, closeDialog, runCompute, isComputing, computeError } = usePluginStore();
  const { getActiveWorksheet } = useWorksheetStore();

  const plugin = activePluginId && activePluginId !== 'doe_create_taguchi' ? getPlugin(activePluginId) : null;
  const sheet = getActiveWorksheet();

  const [formData, setFormData] = useState<Record<string, any>>({});
  const [selectedColumnInList, setSelectedColumnInList] = useState<string | null>(null);
  const [focusedInputName, setFocusedInputName] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [columnSearchFilter, setColumnSearchFilter] = useState<string>('');

  // Sub-Modal & Help States
  const [activeSubModal, setActiveSubModal] = useState<string | null>(null);
  const [isHelpOpen, setIsHelpOpen] = useState<boolean>(false);

  // Initialize form defaults from schema and smart autofill
  useEffect(() => {
    if (!plugin || !plugin.param_schema) return;
    const initialValues: Record<string, any> = {};
    const schemaProps = plugin.param_schema.properties || {};

    Object.entries(schemaProps).forEach(([key, prop]: [string, any]) => {
      if (prop.default !== undefined) {
        initialValues[key] = prop.default;
      } else if (prop.type === 'array' || prop.ui_type === 'column_multi_picker') {
        initialValues[key] = [];
      } else if (prop.type === 'boolean') {
        initialValues[key] = false;
      } else {
        initialValues[key] = '';
      }
    });

    // Dynamic autofill for DOE Analysis modules (Factorial, RSM, Mixture, Taguchi)
    const isDoeAnalysis = ['doe_analyze_factorial', 'doe_analyze_rsm', 'doe_analyze_mixture', 'doe_analyze_taguchi'].includes(plugin.id);
    if (isDoeAnalysis && sheet) {
      const METADATA_COLS = ['stdorder', 'runorder', 'pttype', 'blocks', 'run', 'order', 'centerpt', 'standardorder', 'run_order', 'std_order'];

      // Find response column
      const respColObj = sheet.columns.find((c) => {
        const n = (c.name || '').trim().toLowerCase();
        return /^response_1/i.test(n) || /^response/i.test(n) || /^yield/i.test(n) || /^y$/i.test(n);
      });
      const respColName = respColObj?.name || 'Response_1';

      let factorList: string[] = [];
      if (sheet.designMeta?.factorNames && sheet.designMeta.factorNames.length > 0) {
        factorList = [...sheet.designMeta.factorNames];
      } else {
        const genuineCols = sheet.columns.filter((c) => {
          const name = (c.name || '').trim();
          const lower = name.toLowerCase();
          if (!name) return false;
          if (METADATA_COLS.includes(lower)) return false;
          if (name.toLowerCase().startsWith('response')) return false;
          if (/^c\d+$/i.test(name)) return false;
          return true;
        });
        factorList = genuineCols.map((c) => c.name);
      }

      if (plugin.id === 'doe_analyze_mixture') {
        initialValues['component_cols'] = factorList;
        initialValues['response_col'] = respColName;
      } else {
        initialValues['factor_cols'] = factorList;
        initialValues['response_col'] = respColName;
      }

      if (plugin.id === 'doe_analyze_taguchi') {
        initialValues['sn_ratio_type'] = initialValues['sn_ratio_type'] || 'larger';
      }
    }

    setFormData(initialValues);
    setValidationError(null);
    setActiveSubModal(null);
    setIsHelpOpen(false);

    // Auto focus first column picker input
    const firstColKey = Object.keys(schemaProps).find(
      (k) => schemaProps[k].ui_type === 'column_picker' || schemaProps[k].ui_type === 'column_multi_picker' || schemaProps[k].type === 'array'
    );
    if (firstColKey) {
      setFocusedInputName(firstColKey);
    }
  }, [plugin, sheet]);

  const CUSTOM_MODAL_IDS = ['doe_create_factorial', 'doe_create_rsm', 'doe_create_mixture', 'doe_create_taguchi'];
  if (!activePluginId || CUSTOM_MODAL_IDS.includes(activePluginId)) {
    return null;
  }

  if (!plugin || !sheet) {
    return null;
  }

  const schemaProps = plugin.param_schema?.properties || {};
  const requiredFields: string[] = plugin.param_schema?.required || [];

  // Categorize properties by sub-modal tag
  const subModalGroups: Record<string, string[]> = {};
  const mainFieldNames: string[] = [];

  Object.entries(schemaProps).forEach(([fieldName, prop]: [string, any]) => {
    const subModalName = prop.sub_modal || prop.json_schema_extra?.sub_modal;
    if (subModalName) {
      if (!subModalGroups[subModalName]) {
        subModalGroups[subModalName] = [];
      }
      subModalGroups[subModalName].push(fieldName);
    } else {
      mainFieldNames.push(fieldName);
    }
  });

  const availableSubModals = Object.keys(subModalGroups);

  // Available worksheet columns (showing non-empty columns with C1, C2-T, C3-D tags)
  const availableColumns = sheet.columns
    .filter((c, idx) => Boolean((c.name && c.name.trim() !== '') || sheet.rows.some((r) => r[c.id] !== undefined && r[c.id] !== null && r[c.id] !== '')))
    .map((c) => {
      const idx = sheet.columns.findIndex((col) => col.id === c.id);
      const tag = c.type === 'text' ? `C${idx + 1}-T` : c.type === 'date' ? `C${idx + 1}-D` : `C${idx + 1}`;
      return {
        id: c.id,
        label: c.name ? `${c.name} (${tag})` : tag,
        rawName: c.name || c.id,
        type: c.type,
      };
    })
    .filter((c) => {
      if (!columnSearchFilter.trim()) return true;
      const q = columnSearchFilter.toLowerCase();
      return c.label.toLowerCase().includes(q) || c.rawName.toLowerCase().includes(q);
    });

  const handleSelectColumnToInput = (colName: string) => {
    if (!focusedInputName) {
      const firstCol = Object.keys(schemaProps).find(
        (k) => schemaProps[k].ui_type === 'column_picker' || schemaProps[k].ui_type === 'column_multi_picker' || schemaProps[k].type === 'array'
      );
      if (firstCol) {
        setFocusedInputName(firstCol);
        insertColumnToField(firstCol, colName);
      }
    } else {
      insertColumnToField(focusedInputName, colName);
    }
  };

  const insertColumnToField = (fieldName: string, colName: string) => {
    const prop = schemaProps[fieldName];
    if (!prop) return;

    if (prop.ui_type === 'column_multi_picker' || prop.type === 'array') {
      const currentList: string[] = Array.isArray(formData[fieldName]) ? [...formData[fieldName]] : [];
      if (!currentList.includes(colName)) {
        currentList.push(colName);
        setFormData({ ...formData, [fieldName]: currentList });
      }
    } else {
      setFormData({ ...formData, [fieldName]: colName });
    }
  };

  const handleRemoveFromMultiPicker = (fieldName: string, colName: string) => {
    const currentList: string[] = Array.isArray(formData[fieldName]) ? [...formData[fieldName]] : [];
    const filtered = currentList.filter((c) => c !== colName);
    setFormData({ ...formData, [fieldName]: filtered });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    // Basic frontend required validation
    for (const req of requiredFields) {
      const val = formData[req];
      if (val === undefined || val === null || val === '' || (Array.isArray(val) && val.length === 0)) {
        setValidationError(`Please specify a value for "${schemaProps[req]?.description || req}".`);
        return;
      }
    }

    const success = await runCompute(plugin.id, formData);
    if (success) {
      closeDialog();
    }
  };

  const renderField = (name: string, prop: any) => {
    const isRequired = requiredFields.includes(name);
    const value = formData[name];
    const isFocused = focusedInputName === name;

    // Do not render nominal_target independently since it is rendered contextually with Nominal is best
    if (name === 'nominal_target') {
      return null;
    }

    // 1. Single Column Picker
    if (prop.ui_type === 'column_picker' || prop.json_schema_extra?.ui_type === 'column_picker') {
      return (
        <Field
          key={name}
          label={{
            children: (
              <span className="text-xs font-semibold text-[#323130]">
                {prop.description || name} {isRequired && <span className="text-red-500">*</span>}
              </span>
            ),
          }}
          className="mb-3"
        >
          <div className="relative">
            <Input
              size="small"
              value={value || ''}
              onChange={(_, data) => setFormData({ ...formData, [name]: data.value })}
              onFocus={() => setFocusedInputName(name)}
              placeholder="Select variable from list or type..."
              className="w-full"
              style={{
                borderColor: isFocused ? '#008450' : undefined,
              }}
            />
          </div>
        </Field>
      );
    }

    // 2. Multi Column Picker
    if (
      prop.ui_type === 'column_multi_picker' ||
      prop.json_schema_extra?.ui_type === 'column_multi_picker' ||
      (prop.type === 'array' && !prop.enum)
    ) {
      const selectedCols: string[] = Array.isArray(value) ? value : [];

      return (
        <Field
          key={name}
          label={{
            children: (
              <span className="text-xs font-semibold text-[#323130]">
                {prop.description || name} {isRequired && <span className="text-red-500">*</span>}
              </span>
            ),
          }}
          className="mb-3"
        >
          <div
            onClick={() => setFocusedInputName(name)}
            className={`min-h-[34px] p-1.5 bg-white border rounded-md cursor-text flex flex-wrap gap-1 items-center transition-all ${
              isFocused ? 'border-[#008450] ring-1 ring-[#008450]' : 'border-[#d2d0ce]'
            }`}
          >
            {selectedCols.map((col) => (
              <span
                key={col}
                className="inline-flex items-center gap-1 px-2 py-0.5 bg-[#e6faf0] text-[#008450] border border-[#bbf2d6] rounded text-xs font-medium"
              >
                <span>{col}</span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRemoveFromMultiPicker(name, col);
                  }}
                  className="hover:text-red-600 focus:outline-none"
                >
                  <DismissCircleRegular className="w-3 h-3" />
                </button>
              </span>
            ))}
            {selectedCols.length === 0 && (
              <span className="text-xs text-[#a19f9d] px-1 italic">
                Double-click or select variables from left list...
              </span>
            )}
          </div>
        </Field>
      );
    }

    // 3. Dropdown / Enum / Select
    if (
      prop.enum ||
      prop.options ||
      prop.json_schema_extra?.options ||
      prop.ui_type === 'select' ||
      prop.ui_type === 'dropdown' ||
      prop.json_schema_extra?.ui_type === 'select' ||
      name === 'sn_ratio_type'
    ) {
      const isSNRatio = name === 'sn_ratio_type';
      const rawOptions = prop.options || prop.json_schema_extra?.options || prop.enum;

      let optionList: { value: string; label: string }[] = [];
      if (isSNRatio) {
        optionList = [
          { value: 'larger', label: 'Larger is better' },
          { value: 'smaller', label: 'Smaller is better' },
          { value: 'nominal', label: 'Nominal is best' },
        ];
      } else if (Array.isArray(rawOptions)) {
        optionList = rawOptions.map((opt: any) =>
          typeof opt === 'object' && opt !== null
            ? { value: String(opt.value), label: String(opt.label || opt.value) }
            : { value: String(opt), label: String(opt) }
        );
      }

      const defaultOptVal = optionList[0]?.value || '';
      const curVal = value !== undefined && value !== '' ? String(value) : defaultOptVal;

      return (
        <Field
          key={name}
          label={{
            children: (
              <span className="text-xs font-semibold text-[#323130]">
                {prop.description || name} {isRequired && <span className="text-red-500">*</span>}
              </span>
            ),
          }}
          className="mb-3"
        >
          <div className="space-y-2">
            <select
              value={curVal}
              onChange={(e) => setFormData({ ...formData, [name]: e.target.value })}
              className="w-full px-2.5 py-1.5 text-xs bg-white border border-[#d2d0ce] focus:border-[#008450] rounded-md outline-none text-[#201f1e] font-sans font-medium"
            >
              {optionList.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            {isSNRatio && curVal === 'nominal' && (
              <div className="p-2.5 bg-[#f8f9fa] border border-[#d2d0ce] rounded-md space-y-1 animate-in fade-in duration-100">
                <label className="block text-xs font-semibold text-[#323130]">
                  Nominal Target Value (T) <span className="text-[#008450] font-normal">(Value to aim for)</span>
                </label>
                <Input
                  size="small"
                  type="number"
                  step="any"
                  value={formData['nominal_target'] !== undefined && formData['nominal_target'] !== null ? String(formData['nominal_target']) : ''}
                  onChange={(_, data) => {
                    const parsed = data.value === '' ? '' : Number(data.value);
                    setFormData({ ...formData, nominal_target: parsed });
                  }}
                  placeholder="Enter target value (e.g. 10.0, 25, 100)..."
                  className="w-full"
                />
              </div>
            )}

            {isSNRatio && (
              <MathFormulaCard snType={curVal} targetVal={formData['nominal_target']} />
            )}
          </div>
        </Field>
      );
    }

    // 4. Boolean Checkbox
    if (prop.type === 'boolean') {
      return (
        <div key={name} className="py-1">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={Boolean(value)}
              onChange={(e) => setFormData({ ...formData, [name]: e.target.checked })}
              className="w-4 h-4 text-[#008450] border-[#d2d0ce] rounded cursor-pointer accent-[#008450]"
            />
            <span className="text-xs font-medium text-[#323130]">
              {prop.description || name}
            </span>
          </label>
        </div>
      );
    }

    // 5. Numeric Input
    if (prop.type === 'number' || prop.type === 'integer') {
      return (
        <Field
          key={name}
          label={{
            children: (
              <span className="text-xs font-semibold text-[#323130]">
                {prop.description || name} {isRequired && <span className="text-red-500">*</span>}
              </span>
            ),
          }}
          className="mb-3"
        >
          <Input
            size="small"
            type="number"
            step={prop.type === 'integer' ? '1' : 'any'}
            value={value !== undefined && value !== null ? String(value) : ''}
            onChange={(_, data) => {
              const parsed = data.value === '' ? '' : Number(data.value);
              setFormData({ ...formData, [name]: parsed });
            }}
            placeholder={prop.default !== undefined ? `Default: ${prop.default}` : ''}
            className="w-full"
          />
        </Field>
      );
    }

    // 6. Generic Text Input
    return (
      <Field
        key={name}
        label={{
          children: (
            <span className="text-xs font-semibold text-[#323130]">
              {prop.description || name} {isRequired && <span className="text-red-500">*</span>}
            </span>
          ),
        }}
        className="mb-3"
      >
        <Input
          size="small"
          type="text"
          value={value || ''}
          onChange={(_, data) => setFormData({ ...formData, [name]: data.value })}
          className="w-full"
        />
      </Field>
    );
  };

  return (
    <>
      <div
        className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-[1px] p-4 select-none animate-in fade-in duration-100"
        onClick={(e) => {
          if (e.target === e.currentTarget && !activeSubModal && !isHelpOpen) closeDialog();
        }}
      >
        <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-full max-w-2xl overflow-hidden flex flex-col max-h-[88vh] animate-in zoom-in-95 duration-100">
          {/* Fluent Dialog Header */}
          <div className="flex items-center justify-between px-5 py-3.5 bg-[#f8f9fa] border-b border-[#e0e0e0]">
            <div className="flex items-center space-x-2.5">
              <span className="w-5 h-5 rounded bg-emerald-50 text-[#008450] flex items-center justify-center border border-emerald-200 shrink-0">
                {getMenuOrPluginIcon(plugin.id, plugin.id)}
              </span>
              <h2 className="text-sm font-bold text-[#201f1e]">
                {plugin.name}
              </h2>
            </div>

            <div className="flex items-center gap-1">
              <Button
                appearance="subtle"
                size="small"
                icon={<QuestionCircleRegular className="text-[#008450]" />}
                onClick={() => setIsHelpOpen(true)}
                title="Help & Guidelines"
              />
              <Button
                appearance="subtle"
                size="small"
                icon={<DismissRegular />}
                onClick={closeDialog}
                style={{ minWidth: '28px', padding: 0 }}
              />
            </div>
          </div>

          {/* Dialog Body (Classic Two Column Minitab Layout + Sub-Modal Side Controls) */}
          <form onSubmit={handleSubmit} className="flex flex-col overflow-hidden">
            <div className="p-5 flex gap-5 max-h-[62vh] overflow-y-auto">
              {/* Left Column: Worksheet Available Variables List */}
              <div className="w-48 shrink-0 flex flex-col border border-[#d2d0ce] rounded-lg bg-[#faf9f8] p-2.5">
                <div className="flex items-center justify-between text-xs font-semibold text-[#605e5c] pb-1.5 border-b border-[#edebe9] mb-1.5">
                  <span className="flex items-center gap-1">
                    <TableRegular className="text-[#008450]" />
                    <span>Variables</span>
                  </span>
                  <span className="text-[10px] text-[#8a8886]">
                    {availableColumns.length}
                  </span>
                </div>

                {/* Variable Search Filter */}
                <div className="mb-2">
                  <Input
                    size="small"
                    placeholder="Search vars..."
                    value={columnSearchFilter}
                    onChange={(_, d) => setColumnSearchFilter(d.value)}
                    contentBefore={<SearchRegular className="text-gray-400 w-3 h-3" />}
                    className="w-full text-xs"
                  />
                </div>

                <div className="flex-1 overflow-y-auto space-y-0.5 max-h-52 min-h-[150px]">
                  {availableColumns.map((col) => {
                    const isSelected = selectedColumnInList === col.rawName;

                    return (
                      <div
                        key={col.id}
                        onClick={() => setSelectedColumnInList(col.rawName)}
                        onDoubleClick={() => handleSelectColumnToInput(col.rawName)}
                        className={`px-2 py-1 rounded text-xs cursor-pointer truncate transition-colors flex items-center justify-between ${
                          isSelected
                            ? 'bg-[#008450] text-white font-semibold'
                            : 'hover:bg-[#e6faf0] text-[#323130]'
                        }`}
                        title={`${col.label} (Double-click to insert)`}
                      >
                        <span className="truncate">{col.label}</span>
                      </div>
                    );
                  })}
                </div>

                <Button
                  type="button"
                  appearance="secondary"
                  size="small"
                  icon={<ArrowRightRegular />}
                  iconPosition="after"
                  disabled={!selectedColumnInList}
                  onClick={() => selectedColumnInList && handleSelectColumnToInput(selectedColumnInList)}
                  className="mt-2 w-full text-xs font-medium"
                >
                  Select
                </Button>
              </div>

              {/* Right Column: Main Form Parameters & Sub-Modal Launcher Strip */}
              <div className="flex-1 space-y-2">
                {availableColumns.length === 0 && (
                  <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-md text-xs text-amber-800 flex items-center gap-2">
                    <InfoRegular className="w-4 h-4 shrink-0 text-amber-600" />
                    <span>No data columns detected in active worksheet. Please load a sample dataset or enter data first.</span>
                  </div>
                )}

                {validationError && (
                  <div className="p-2.5 bg-red-50 border border-red-200 rounded-md text-xs text-red-700 flex items-center gap-2">
                    <InfoRegular className="w-4 h-4 shrink-0 text-red-600" />
                    <span>{validationError}</span>
                  </div>
                )}

                {computeError && (
                  <div className="p-2.5 bg-red-50 border border-red-200 rounded-md text-xs text-red-700 flex items-center gap-2">
                    <InfoRegular className="w-4 h-4 shrink-0 text-red-600" />
                    <span>{computeError}</span>
                  </div>
                )}

                {/* Main Fields */}
                <div className="space-y-1">
                  {mainFieldNames.map((fieldName) =>
                    renderField(fieldName, schemaProps[fieldName])
                  )}
                </div>

                {/* Sub-Modal Launcher Buttons (e.g. Time Scale..., Graph Options..., Storage..., Results..., Options...) */}
                {availableSubModals.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-[#edebe9]">
                    <span className="block text-[11px] font-semibold text-[#605e5c] uppercase tracking-wider mb-2">
                      Options & Sub-Dialogs
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {availableSubModals.map((subModalName) => (
                        <Button
                          key={subModalName}
                          type="button"
                          appearance="secondary"
                          size="small"
                          icon={<OptionsRegular className="text-[#008450]" />}
                          onClick={() => setActiveSubModal(subModalName)}
                          className="text-xs font-medium"
                        >
                          {subModalName}
                        </Button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Fluent Dialog Actions Footer */}
            <div className="px-5 py-3 bg-[#f8f9fa] border-t border-[#e0e0e0] flex items-center justify-between">
              <div className="text-[11px] text-[#8a8886] truncate max-w-[200px]">
                {plugin.menu_path?.join(' / ') || plugin.id}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  appearance="subtle"
                  size="medium"
                  icon={<QuestionCircleRegular />}
                  onClick={() => setIsHelpOpen(true)}
                >
                  Help
                </Button>
                <Button
                  type="button"
                  appearance="secondary"
                  size="medium"
                  onClick={closeDialog}
                  disabled={isComputing}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  appearance="primary"
                  size="medium"
                  disabled={isComputing}
                  icon={isComputing ? <Spinner size="tiny" /> : undefined}
                >
                  {isComputing ? 'Computing...' : 'OK'}
                </Button>
              </div>
            </div>
          </form>
        </div>
      </div>

      {/* Sub-Modal Dialog Popup */}
      {activeSubModal && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/30 backdrop-blur-[0.5px] p-4 select-none animate-in fade-in duration-100">
          <div className="bg-white rounded-lg shadow-2xl border border-[#008450]/40 w-full max-w-md overflow-hidden flex flex-col max-h-[80vh] animate-in zoom-in-95 duration-100">
            <div className="flex items-center justify-between px-4 py-3 bg-[#f8f9fa] border-b border-[#e0e0e0]">
              <div className="flex items-center space-x-2">
                <SettingsRegular className="text-[#008450] w-4 h-4" />
                <h3 className="text-xs font-bold text-[#201f1e]">
                  {plugin.name} - {activeSubModal}
                </h3>
              </div>
              <Button
                appearance="subtle"
                size="small"
                icon={<DismissRegular />}
                onClick={() => setActiveSubModal(null)}
                style={{ minWidth: '24px', padding: 0 }}
              />
            </div>

            <div className="p-4 space-y-2 overflow-y-auto max-h-[55vh]">
              {subModalGroups[activeSubModal]?.map((fieldName) =>
                renderField(fieldName, schemaProps[fieldName])
              )}
            </div>

            <div className="px-4 py-2.5 bg-[#f8f9fa] border-t border-[#e0e0e0] flex items-center justify-end gap-2">
              <Button
                type="button"
                appearance="primary"
                size="small"
                onClick={() => setActiveSubModal(null)}
              >
                OK
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Help Modal */}
      {isHelpOpen && (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/40 backdrop-blur-[1px] p-4 select-none animate-in fade-in duration-100">
          <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-full max-w-xl overflow-hidden flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-100">
            <div className="flex items-center justify-between px-5 py-3.5 bg-[#008450] text-white">
              <div className="flex items-center space-x-2">
                <QuestionCircleRegular className="w-5 h-5 text-white" />
                <h3 className="text-sm font-bold">
                  Help: {plugin.name}
                </h3>
              </div>
              <Button
                appearance="subtle"
                size="small"
                icon={<DismissRegular className="text-white" />}
                onClick={() => setIsHelpOpen(false)}
                style={{ minWidth: '28px', padding: 0, color: 'white' }}
              />
            </div>

            <div className="p-5 space-y-3.5 overflow-y-auto text-xs text-[#323130] leading-relaxed">
              <div className="p-3 bg-[#e6faf0] border border-[#bbf2d6] rounded-md">
                <span className="font-semibold text-[#008450] block mb-1">Method Overview</span>
                <p>{plugin.description}</p>
              </div>

              <div className="space-y-1.5">
                <span className="font-semibold text-[#201f1e] block text-xs">Menu Location:</span>
                <p className="font-mono bg-gray-100 px-2.5 py-1 rounded text-[11px] text-gray-700 inline-block">
                  {plugin.menu_path?.join(' > ')}
                </p>
              </div>

              <div className="space-y-1.5">
                <span className="font-semibold text-[#201f1e] block text-xs">Standard Guidelines & Output Interpretation:</span>
                <ul className="list-disc pl-4 space-y-1 text-gray-700">
                  <li><strong>Accuracy Measures:</strong> Low values of MAPE, MAD, and MSD indicate a superior model fit.</li>
                  <li><strong>Storage Options:</strong> Check <em>Storage...</em> options to append calculated values (Fits, Residuals, Forecasts) directly to your active worksheet.</li>
                  <li><strong>Time Scale / Lags:</strong> Set custom time intervals, seasonal period lengths, and prediction limits via the corresponding sub-dialogs.</li>
                </ul>
              </div>
            </div>

            <div className="px-5 py-3 bg-[#f8f9fa] border-t border-[#e0e0e0] flex items-center justify-end">
              <Button
                type="button"
                appearance="primary"
                size="small"
                onClick={() => setIsHelpOpen(false)}
              >
                Close Help
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

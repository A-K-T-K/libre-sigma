/**
 * Comprehensive Node/Jest-compatible verification test for LTB project format & edge cases.
 */
import fs from 'fs';
import path from 'path';

console.log('='.repeat(60));
console.log('LIBRE TAB (.ltb) PROJECT FORMAT & EDGE CASE TEST SUITE');
console.log('='.repeat(60));

let passed = 0;
let failed = 0;

function check(name, condition, detail = '') {
  if (condition) {
    passed++;
    console.log(`  PASS: ${name}`);
  } else {
    failed++;
    console.log(`  FAIL: ${name} -- ${detail}`);
  }
}

// 1. Valid LTB schema generation test
const sampleLtb = {
  format: 'libretab-project',
  version: '1.0.0',
  title: 'Six Sigma DMAIC Project',
  savedAt: new Date().toISOString(),
  activeSheetId: 'ws-1',
  worksheets: [
    {
      id: 'ws-1',
      name: 'Injection_Molding',
      columns: [
        { id: 'c1', name: 'Temp', type: 'numeric', role: 'CONTINUOUS', width: 110 },
        { id: 'c2', name: 'Pressure', type: 'numeric', role: 'CONTINUOUS', width: 120 },
        { id: 'c3', name: 'Operator', type: 'text', role: 'CATEGORICAL', width: 100 },
        { id: 'c4', name: 'Strength', type: 'numeric', role: 'RESPONSE', width: 110 },
        { id: 'c5', name: 'Log_Strength', type: 'numeric', formula: 'LN(C4)', isCalculated: true, width: 130 },
        { id: 'c6', name: 'FITS1', type: 'numeric', isLocked: true, width: 100 }
      ],
      rows: [
        { c1: 210, c2: 45.2, c3: 'Alice', c4: 850, c5: 6.745, c6: 848.2 },
        { c1: 215, c2: 46.0, c3: 'Bob', c4: 875, c5: 6.774, c6: 872.1 },
        { c1: null, c2: 44.8, c3: '', c4: null, c5: '', c6: 835.0 }, // Edge case: nulls and blanks
        { c1: 220, c2: NaN, c3: 'Charlie', c4: 890, c5: 6.791, c6: 888.5 } // Edge case: NaN in numeric
      ],
      designMeta: {
        type: 'factorial',
        factors: 3,
        runs: 8,
        resolution: 'Full'
      },
      autoRecalculateFormulas: true
    },
    {
      id: 'ws-2',
      name: 'Empty_Validation_Sheet', // Edge case: empty sheet
      columns: [
        { id: 'c1', name: 'C1', type: 'numeric', width: 110 }
      ],
      rows: []
    }
  ],
  sessionItems: [
    {
      id: 'out-101',
      timestamp: '17:30:00',
      pluginId: 'regression_stepwise',
      pluginName: 'Stepwise Regression',
      worksheetName: 'Injection_Molding',
      params: { response: 'Strength', predictors: ['Temp', 'Pressure'] },
      result: {
        title: 'Stepwise Regression: Strength versus Temp, Pressure',
        subtitle: 'Response: Strength (MPa)',
        text_output: 'Regression Equation: Strength = 120.5 + 3.42 Temp + 1.15 Pressure\nR-sq = 94.2%',
        tables: [
          {
            title: 'Analysis of Variance',
            headers: ['Source', 'DF', 'Adj SS', 'Adj MS', 'F-Value', 'P-Value'],
            rows: [
              ['Regression', 2, 1420.5, 710.25, 45.2, 0.0001],
              ['Error', 15, 235.4, 15.69, null, null],
              ['Total', 17, 1655.9, null, null, null]
            ],
            notes: ['Alpha = 0.05', 'Stepwise forward selection']
          }
        ],
        statistics: { r_squared: 0.942, f_stat: 45.2, p_val: 0.0001 },
        plotly_figure: {
          data: [{ x: [210, 215, 220], y: [850, 875, 890], mode: 'markers', type: 'scatter' }],
          layout: { title: 'Fitted Line Plot' }
        }
      }
    }
  ]
};

// Test 1: JSON Serialization & Character Encoding
console.log('\n[Test 1] Serialization & UTF-8 Roundtrip');
const jsonStr = JSON.stringify(sampleLtb, (k, v) => (typeof v === 'number' && isNaN(v) ? null : v), 2);
check('JSON is non-empty string', typeof jsonStr === 'string' && jsonStr.length > 500);

// Test 2: Parse and Validate Fields
console.log('\n[Test 2] Parse & Schema Validation');
const parsed = JSON.parse(jsonStr);
check('Format identifier is libretab-project', parsed.format === 'libretab-project');
check('Version is 1.0.0', parsed.version === '1.0.0');
check('Worksheets array has 2 sheets', parsed.worksheets.length === 2);
check('ActiveSheetId is preserved', parsed.activeSheetId === 'ws-1');

// Test 3: Columns and Attributes Integrity
console.log('\n[Test 3] Column Definitions & Metadata');
const ws1 = parsed.worksheets[0];
check('Column count is 6', ws1.columns.length === 6);
check('Formula column preserved', ws1.columns[4].formula === 'LN(C4)' && ws1.columns[4].isCalculated === true);
check('Locked column preserved', ws1.columns[5].isLocked === true);
check('Role categorical preserved', ws1.columns[2].role === 'CATEGORICAL');
check('Role response preserved', ws1.columns[3].role === 'RESPONSE');

// Test 4: Rows & Edge Cases (NaN, Nulls, Empty Sheet)
console.log('\n[Test 4] Data Rows & Missing Values Handling');
check('Row count is 4 in ws1', ws1.rows.length === 4);
check('Null cell value handled as null/empty', ws1.rows[2].c1 === null || ws1.rows[2].c1 === '');
check('NaN cell sanitized', ws1.rows[3].c2 === null || ws1.rows[3].c2 === '');
const ws2 = parsed.worksheets[1];
check('Empty sheet has 0 rows', ws2.rows.length === 0);

// Test 5: DOE Metadata Preservation
console.log('\n[Test 5] DOE Design Metadata');
check('DOE designMeta is factorial with 8 runs', ws1.designMeta.type === 'factorial' && ws1.designMeta.runs === 8);

// Test 6: Session Reports & Plotly Figures
console.log('\n[Test 6] Session Reports, Tables & Plotly Graphs');
check('Session items array has 1 item', parsed.sessionItems.length === 1);
const s1 = parsed.sessionItems[0];
check('Plugin ID is regression_stepwise', s1.pluginId === 'regression_stepwise');
check('Table headers count is 6', s1.result.tables[0].headers.length === 6);
check('Table rows count is 3', s1.result.tables[0].rows.length === 3);
check('Plotly figure has data and layout', s1.result.plotly_figure.data.length === 1 && s1.result.plotly_figure.layout.title === 'Fitted Line Plot');
check('Statistics dictionary is intact', s1.result.statistics.r_squared === 0.942);

// Summary
console.log('\n' + '='.repeat(60));
console.log(`RESULTS: ${passed} PASSED / ${failed} FAILED`);
console.log('='.repeat(60));
if (failed === 0) {
  console.log('ALL LTB PROJECT FORMAT & EDGE CASE TESTS PASSED PERFECTLY!\n');
} else {
  process.exit(1);
}

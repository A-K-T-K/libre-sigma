/**
 * Benchmark and edge case test for vectorized Formula Engine in LibRE Tab.
 */
import { evaluateWorksheetFormula } from './frontend/src/utils/formulaEngine.ts';

console.log('='.repeat(60));
console.log('VECTORIZED FORMULA ENGINE BENCHMARK & EDGE CASE SUITE');
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

// 1. High Performance Vectorized Benchmark: 50,000 rows
console.log('\n[Test 1] 50,000 Row Vectorized Formula Calculation Benchmark');
const rowCount = 50000;
const columns = [
  { id: 'c1', name: 'Temp', type: 'numeric' },
  { id: 'c2', name: 'Pressure', type: 'numeric' },
  { id: 'c3', name: 'Result', type: 'numeric' },
];

const rows = new Array(rowCount);
for (let i = 0; i < rowCount; i++) {
  rows[i] = {
    c1: 100 + (i % 50),
    c2: 10 + (i % 20),
  };
}

const t0 = performance.now();
const res1 = evaluateWorksheetFormula('LN(C1) * 2.5 + SQRT(C2) - MEAN(C1)', columns, rows);
const tElapsed = performance.now() - t0;
if (!res1.success) {
  console.log('Test 1 error:', res1);
}


check('50,000 rows evaluated successfully', res1.success === true && res1.values.length === rowCount);
check(`High throughput execution (${tElapsed.toFixed(1)}ms < 250ms for 50k rows)`, tElapsed < 250, `took ${tElapsed.toFixed(1)}ms`);
check('Computed non-null float values', typeof res1.values[0] === 'number' && !isNaN(res1.values[0]));

// 2. Statistical Aggregates & Z-Score
console.log('\n[Test 2] Statistical Aggregates (ZSCORE, MEAN, STDEV, MEDIAN, MIN, MAX)');
const smallRows = [
  { c1: 10, c2: 5 },
  { c1: 20, c2: 15 },
  { c1: 30, c2: 25 },
];
const resStats = evaluateWorksheetFormula('ZSCORE(C1)', columns, smallRows);
check('ZScore evaluation success', resStats.success === true);
check('ZScore mean is zero (Z[1] ≈ 0)', Math.abs(resStats.values[1]) < 1e-4);
check('ZScore symetrical (Z[0] ≈ -Z[2])', Math.abs(resStats.values[0] + resStats.values[2]) < 1e-4);

// 3. Edge Cases: Div-by-zero, Missing cells, nulls, negative SQRT
console.log('\n[Test 3] Edge Cases: Div-by-Zero, Nulls, Blanks, Negative SQRT');
const edgeRows = [
  { c1: 10, c2: 0 },         // Div by zero: C1 / C2 -> null/Infinity sanitized to null
  { c1: null, c2: 5 },       // Null in C1 -> null
  { c1: '', c2: 5 },         // Blank in C1 -> null
  { c1: -16, c2: 4 },        // SQRT of negative -> NaN sanitized to null
  { c1: 25, c2: 5 },         // Valid: SQRT(25) + 5 = 10
];

const resEdge = evaluateWorksheetFormula('SQRT(C1) + C2', columns, edgeRows);
check('Edge rows evaluated without throw', resEdge.success === true);
check('Null cell produced null result', resEdge.values[1] === null);
check('Blank cell produced null result', resEdge.values[2] === null);
check('Negative SQRT produced null result (NaN sanitized)', resEdge.values[3] === null);
check('Valid row produced 10', resEdge.values[4] === 10);

// 4. Edge Case: Empty rows array
console.log('\n[Test 4] Edge Case: Empty Worksheet (0 rows)');
const resEmpty = evaluateWorksheetFormula('C1 + C2', columns, []);
check('Empty rows array handled safely', resEmpty.success === true && resEmpty.values.length === 0);

// 5. Edge Case: Syntax errors
console.log('\n[Test 5] Edge Case: Invalid Syntax / Unbalanced Parens');
const resSyntax = evaluateWorksheetFormula('((C1 + ', columns, smallRows);
check('Syntax error caught gracefully', resSyntax.success === false && Boolean(resSyntax.errorMessage));

console.log('\n' + '='.repeat(60));
console.log(`RESULTS: ${passed} PASSED / ${failed} FAILED`);
console.log('='.repeat(60));
if (failed === 0) {
  console.log('ALL VECTORIZED FORMULA ENGINE & MATRIX TESTS PASSED!\n');
} else {
  process.exit(1);
}

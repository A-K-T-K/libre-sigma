const { spawn } = require('child_process');
const os = require('os');
const path = require('path');
const fs = require('fs');

const cargoBin = path.join(os.homedir(), '.cargo', 'bin');
const nodeBin = path.dirname(process.execPath);

// Locate Path variable in environment
let pathKey = Object.keys(process.env).find((k) => k.toLowerCase() === 'path') || 'Path';
let currentPath = process.env[pathKey] || '';

// Prepend Cargo and Node binaries if missing
const pathsToAdd = [cargoBin, nodeBin].filter((p) => fs.existsSync(p));
const pathList = currentPath.split(path.delimiter);

for (const p of pathsToAdd) {
  if (!pathList.some((existing) => existing.toLowerCase() === p.toLowerCase())) {
    pathList.unshift(p);
  }
}

const updatedPath = pathList.join(path.delimiter);
process.env[pathKey] = updatedPath;
if (pathKey !== 'PATH') process.env.PATH = updatedPath;
if (pathKey !== 'Path') process.env.Path = updatedPath;

const args = process.argv.slice(2);
const tauriArgs = args.length > 0 ? args : ['dev'];

const frontendDir = path.join(__dirname, 'frontend');
const tauriCliScript = path.join(frontendDir, 'node_modules', '@tauri-apps', 'cli', 'tauri.js');

console.log(`[LibRE Sigma] Cargo Bin: ${cargoBin}`);
console.log(`[LibRE Sigma] Executing Tauri CLI: node ${tauriCliScript} ${tauriArgs.join(' ')}`);

const child = spawn(process.execPath, [tauriCliScript, ...tauriArgs], {
  cwd: frontendDir,
  env: process.env,
  stdio: 'inherit',
  shell: false,
});

child.on('error', (err) => {
  console.error('[LibRE Sigma] Failed to start Tauri process:', err);
  process.exit(1);
});

child.on('exit', (code) => {
  process.exit(code || 0);
});

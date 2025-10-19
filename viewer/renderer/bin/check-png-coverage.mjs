#!/usr/bin/env node
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';

function log(...args) { console.log('[check-png-coverage]', ...args); }

function usage() {
  console.error('Usage: check-png-coverage <path/to/results_root>');
}

function getPngPath(sourcePath) {
  const p = path.parse(sourcePath);
  return path.join(p.dir, `${p.name}.png`);
}

async function* walkFiles(dir, exts) {
  let entries;
  try {
    entries = await fsp.readdir(dir, { withFileTypes: true });
  } catch (_) {
    return; // ignore unreadable dirs
  }
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name === '.git' || e.name === 'node_modules' || e.name === '.next' || e.name === 'dist' || e.name === 'build') continue;
      yield* walkFiles(full, exts);
    } else if (e.isFile()) {
      const ext = path.extname(e.name).toLowerCase();
      if (exts.has(ext)) yield full;
    }
  }
}

async function analyzeRun(runDir) {
  const exts = new Set(['.html', '.htm', '.jsx', '.js']);
  let total = 0;
  let withPng = 0;
  for await (const file of walkFiles(runDir, exts)) {
    total += 1;
    const pngPath = getPngPath(file);
    if (fs.existsSync(pngPath)) withPng += 1;
  }
  const missing = Math.max(0, total - withPng);
  const missingPct = total > 0 ? ((missing / total) * 100) : 0;
  return { total, withPng, missing, missingPct };
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 1) {
    usage();
    process.exit(1);
  }
  const resultsRoot = path.resolve(process.cwd(), args[0]);
  if (!fs.existsSync(resultsRoot) || !fs.statSync(resultsRoot).isDirectory()) {
    console.error('Results root not found:', resultsRoot);
    process.exit(1);
  }

  log('Root:', resultsRoot);

  let runDirs = [];
  try {
    runDirs = fs
      .readdirSync(resultsRoot, { withFileTypes: true })
      .filter((d) => d.isDirectory() && d.name !== '.git')
      .map((d) => ({ name: d.name, dir: path.join(resultsRoot, d.name) }));
  } catch (err) {
    console.error('Failed to read results root:', err?.message || err);
    process.exit(1);
  }

  if (!runDirs.length) {
    log('No runs found');
    return;
  }

  let grandTotal = 0;
  let grandWithPng = 0;
  let grandMissing = 0;

  for (const run of runDirs) {
    const { total, withPng, missing, missingPct } = await analyzeRun(run.dir);
    grandTotal += total;
    grandWithPng += withPng;
    grandMissing += missing;
    const pctStr = missingPct.toFixed(1).padStart(5, ' ');
    log(`Run ${run.name}: total=${total} png=${withPng} missing=${missing} missing%=${pctStr}%`);
  }

  const overallMissingPct = grandTotal > 0 ? ((grandMissing / grandTotal) * 100) : 0;
  log(`Overall: total=${grandTotal} png=${grandWithPng} missing=${grandMissing} missing%=${overallMissingPct.toFixed(1)}%`);
}

main().catch((e) => { console.error('[check-png-coverage] Error:', e); process.exit(1); });


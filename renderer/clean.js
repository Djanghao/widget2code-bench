#!/usr/bin/env node
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';

function log(...args) { console.log('[clean]', ...args); }

async function* walk(dir) {
  const entries = await fsp.readdir(dir, { withFileTypes: true });
  for (const e of entries) {
    const full = path.join(dir, e.name);
    // Skip common heavy or irrelevant dirs
    if (e.isDirectory()) {
      if (e.name === 'node_modules' || e.name === '.git' || e.name === '.next' || e.name === 'dist' || e.name === 'build') continue;
      yield* walk(full);
    } else if (e.isFile() && /\.png$/i.test(e.name)) {
      yield full;
    }
  }
}

async function removeFiles(files, concurrency) {
  let idx = 0;
  let removed = 0;
  const errors = [];
  async function worker() {
    while (true) {
      const i = idx++;
      if (i >= files.length) break;
      const file = files[i];
      try {
        await fsp.unlink(file);
        removed++;
      } catch (err) {
        errors.push({ file, error: String(err) });
      }
    }
  }
  const workers = Array.from({ length: concurrency }, () => worker());
  await Promise.all(workers);
  return { removed, errors };
}

async function main() {
  const start = Date.now();
  const root = path.resolve(process.cwd(), process.argv[2] || '.');
  const files = [];
  for await (const f of walk(root)) files.push(f);
  if (files.length === 0) {
    log('No .png files found under:', root);
    return;
  }
  const cpu = os.cpus()?.length || 4;
  const concurrency = Math.min(files.length, Math.max(4, Math.floor(cpu * 2)));
  log('Root:', root);
  log('Found PNG:', files.length);
  const { removed, errors } = await removeFiles(files, concurrency);
  const ms = Date.now() - start;
  log(`Deleted: ${removed}/${files.length} in ${ms}ms`);
  if (errors.length) {
    for (const e of errors.slice(0, 5)) log('ERR', e.file, e.error);
    if (errors.length > 5) log(`... and ${errors.length - 5} more errors`);
    process.exitCode = 1;
  }
}

main().catch((e) => { console.error('[clean] Error:', e); process.exit(1); });


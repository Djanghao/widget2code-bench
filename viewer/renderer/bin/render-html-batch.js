#!/usr/bin/env node
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright';

function log(...args) { console.log('[render-html-batch]', ...args); }

async function* walk(dir) {
  const entries = await fsp.readdir(dir, { withFileTypes: true });
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      yield* walk(full);
    } else if (e.isFile() && /\.html?$/.test(e.name)) {
      yield full;
    }
  }
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 1) {
    console.error('Usage: render-html-batch <folder> [-j N]');
    process.exit(1);
  }

  let dir = '';
  let jobs = undefined;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '-j' || args[i] === '--jobs') {
      jobs = Number(args[++i]);
    } else {
      dir = args[i];
    }
  }
  dir = path.resolve(process.cwd(), dir);
  const files = [];
  for await (const f of walk(dir)) files.push(f);
  if (files.length === 0) {
    log('No .html files found under:', dir);
    return;
  }

  const cpu = os.cpus()?.length || 4;
  const concurrency = Math.max(1, Math.min(files.length, jobs || cpu));
  log('Folder:', dir);
  log('Files:', files.length);
  log('Concurrency:', concurrency);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1200, height: 1000 } });

  try {
    const warm = await context.newPage();
    await warm.setContent(`<!doctype html><html><head>
      <script src="https://cdn.tailwindcss.com"><\/script>
      <script src="https://cdn.jsdelivr.net/npm/lucide@0.292.0/dist/umd/lucide.min.js"><\/script>
    </head><body></body></html>`, { waitUntil: 'load' });
    await warm.close();
  } catch {}

  let idx = 0;
  const results = [];

  async function worker() {
    while (true) {
      const i = idx++;
      if (i >= files.length) break;
      const file = files[i];
      const t0 = Date.now();
      try {
        const page = await context.newPage();
        const fileUrl = pathToFileURL(file).href;
        await page.goto(fileUrl, { waitUntil: 'load' });

        await page.evaluate(() => {
          document.documentElement.style.background = 'transparent';
          if (document.body) {
            document.body.style.background = 'transparent';
            document.body.style.overflow = 'hidden';
          }
        });

        await page.waitForSelector('.widget', { state: 'attached', timeout: 10000 });
        await page.waitForTimeout(60);

        const widget = await page.$('.widget');
        if (!widget) throw new Error('No .widget');

        async function measure() {
          return page.evaluate((el) => {
            const r = el.getBoundingClientRect();
            return { x: r.x, y: r.y, width: r.width, height: r.height };
          }, widget);
        }

        let box = await measure();
        const start = Date.now();
        while ((box.width === 0 || box.height === 0) && Date.now() - start < 3000) {
          await page.waitForTimeout(50);
          box = await measure();
        }

        const vw = Math.max(400, Math.ceil(box.x + box.width + 20));
        const vh = Math.max(400, Math.ceil(box.y + box.height + 20));
        await page.setViewportSize({ width: vw, height: vh });

        const { dir: d, name } = path.parse(file);
        const outPath = path.join(d, `${name}.png`);
        await widget.screenshot({ path: outPath, omitBackground: true });
        await page.close();

        results.push({ file, ok: true, ms: Date.now() - t0, size: `${Math.round(box.width)}x${Math.round(box.height)}` });
      } catch (err) {
        results.push({ file, ok: false, error: String(err) });
      }
    }
  }

  const workers = Array.from({ length: concurrency }, () => worker());
  await Promise.all(workers);
  await browser.close();

  for (const r of results) {
    if (r.ok) {
      log('OK', r.file, r.size, `${r.ms}ms`);
    } else {
      log('FAIL', r.file, r.error);
    }
  }
}

main().catch((e) => { console.error('[render-html-batch] Error:', e); process.exit(1); });

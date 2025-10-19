#!/usr/bin/env node
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { EventEmitter } from 'node:events';
import esbuild from 'esbuild';
import React from 'react';
import ReactDOMServer from 'react-dom/server';
import { chromium } from 'playwright';

EventEmitter.defaultMaxListeners = 20;

function log(...args) { console.log('[render-jsx-batch]', ...args); }

function normalizeJsxToTemp(inputPath, tmpDir) {
  const src = fs.readFileSync(inputPath, 'utf8');
  const replaced = src.replace(/<style>(?!\s*{)([\s\S]*?)<\/style>/g, (m, css) => {
    const safe = css.replace(/`/g, '\\`');
    return `<style>{\`${safe}\`}</style>`;
  });
  const out = path.join(tmpDir, path.basename(inputPath));
  fs.writeFileSync(out, replaced, 'utf8');
  return out;
}

async function buildForNode(inputPath, outFile, workingDir) {
  const viewerRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
  await esbuild.build({
    entryPoints: [inputPath],
    outfile: outFile,
    bundle: true,
    platform: 'node',
    format: 'esm',
    target: ['node18'],
    jsx: 'automatic',
    jsxImportSource: 'react',
    sourcemap: false,
    logLevel: 'silent',
    absWorkingDir: workingDir || viewerRoot,
    nodePaths: [viewerRoot, path.join(viewerRoot, 'node_modules')],
  });
}

async function buildForBrowser(inputPath, outFile, workingDir) {
  const viewerRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
  const entryCode = `import React from 'react';
import { hydrateRoot } from 'react-dom/client';
import Widget from ${JSON.stringify(inputPath)};
const root = document.getElementById('root');
hydrateRoot(root, React.createElement(Widget));`;
  const entryFile = outFile.replace(/\.js$/, '.entry.js');
  fs.writeFileSync(entryFile, entryCode, 'utf8');
  await esbuild.build({
    entryPoints: [entryFile],
    outfile: outFile,
    bundle: true,
    platform: 'browser',
    format: 'iife',
    target: ['es2020'],
    jsx: 'automatic',
    jsxImportSource: 'react',
    sourcemap: false,
    logLevel: 'silent',
    absWorkingDir: workingDir || viewerRoot,
    nodePaths: [viewerRoot, path.join(viewerRoot, 'node_modules')],
    define: { 'process.env.NODE_ENV': '"production"' }
  });
}

function htmlTemplate({ ssrMarkup, includeTailwindCdn = true }) {
  const tailwindScripts = includeTailwindCdn
    ? `\n    <script>window.tailwind=window.tailwind||{};window.tailwind.config={corePlugins:{preflight:false}};<\/script>\n    <script src=\"https://cdn.tailwindcss.com\"><\/script>\n  `
    : '';
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    html,body,#root { margin: 0; padding: 0; background: transparent; }
    body { overflow: hidden; }
    .widget { display: inline-block; }
  </style>
  ${tailwindScripts}
  <title>render-jsx-batch</title>
</head>
<body>
  <div id="root">${ssrMarkup}</div>
</body>
</html>`;
}

async function* walk(dir) {
  const entries = await fsp.readdir(dir, { withFileTypes: true });
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      yield* walk(full);
    } else if (e.isFile() && /\.jsx$/.test(e.name)) {
      const { dir: d, name } = path.parse(full);
      const pngPath = path.join(d, `${name}.png`);
      if (!fs.existsSync(pngPath)) {
        yield full;
      }
    }
  }
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 1) {
    console.error('Usage: render-jsx-batch <folder> [-j N]');
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
  const total = files.length;
  if (total === 0) {
    log('No .jsx files found under:', dir);
    return;
  }
  const cpu = os.cpus()?.length || 4;
  const concurrency = Math.max(1, Math.min(total, jobs || cpu));
  log('Folder:', dir);
  log('Files:', total);
  log('Concurrency:', concurrency);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1200, height: 1000 } });

  try {
    const warm = await context.newPage();
    await warm.setContent(`<!doctype html><html><head>
      <script>window.tailwind=window.tailwind||{};window.tailwind.config={corePlugins:{preflight:false}};<\/script>
      <script src="https://cdn.tailwindcss.com"><\/script>
    </head><body></body></html>`, { waitUntil: 'load' });
    await warm.close();
  } catch {}

  let idx = 0;
  let processed = 0;
  let okCount = 0;
  let failCount = 0;
  const results = [];
  async function worker() {
    while (true) {
      const i = idx++;
      if (i >= files.length) break;
      const file = files[i];
      const t0 = Date.now();
      const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'render-jsx-batch-'));
      const ssrOut = path.join(tmpDir, 'ssr.js');
      const browserOut = path.join(tmpDir, 'client.js');
      const normalizedInput = normalizeJsxToTemp(file, tmpDir);
      const workingDir = path.dirname(file);
      try {
        await buildForNode(normalizedInput, ssrOut, workingDir);
        const mod = await import(pathToFileURL(ssrOut).href);
        const Widget = mod.default || mod.Widget;
        if (!Widget) throw new Error('No default export');
        const ssrMarkup = ReactDOMServer.renderToString(React.createElement(Widget));
        await buildForBrowser(normalizedInput, browserOut, workingDir);
        const html = htmlTemplate({ ssrMarkup, includeTailwindCdn: true });

        const page = await context.newPage();
        await page.setContent(html, { waitUntil: 'load' });
        const clientCode = fs.readFileSync(browserOut, 'utf8');
        await page.addScriptTag({ content: clientCode });
        await page.evaluate(() => { document.body.style.background = 'transparent'; });
        await page.waitForSelector('.widget', { state: 'attached', timeout: 10000 });
        await page.waitForTimeout(60);
        const widget = await page.$('.widget');
        if (!widget) throw new Error('No .widget');
        async function measure() { return page.evaluate(el => { const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; }, widget); }
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
        const ms = Date.now() - t0;
        const size = `${Math.round(box.width)}x${Math.round(box.height)}`;
        results.push({ file, ok: true, ms, size, outPath });
        okCount++;
        processed++;
        const percent = ((processed / total) * 100).toFixed(1);
        log(`[${processed}/${total}] ${percent}% OK`, file, '->', outPath, size, `${ms}ms`);
      } catch (err) {
        const error = String(err?.message || err);
        results.push({ file, ok: false, error });
        failCount++;
        processed++;
        const percent = ((processed / total) * 100).toFixed(1);
        log(`[${processed}/${total}] ${percent}% FAIL`, file, error);
      }
    }
  }

  const workers = Array.from({ length: concurrency }, () => worker());
  await Promise.all(workers);
  await browser.close();

  for (const r of results) {
    if (r.ok) {
      log('OK', r.file, '->', r.outPath, r.size, `${r.ms}ms`);
    } else {
      log('FAIL', r.file, r.error);
    }
  }
  const finalPercent = ((processed / total) * 100).toFixed(1);
  log(`Summary: ${processed}/${total} ${finalPercent}% completed, OK=${okCount} FAIL=${failCount}`);
}

main().catch((e) => { console.error('[render-jsx-batch] Error:', e); process.exit(1); });

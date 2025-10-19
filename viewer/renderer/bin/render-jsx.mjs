#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import url from 'node:url';
import { fileURLToPath, pathToFileURL } from 'node:url';
import esbuild from 'esbuild';
import React from 'react';
import ReactDOMServer from 'react-dom/server';
import { chromium } from 'playwright';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function log(...args) {
  console.log('[render-jsx]', ...args);
}

async function buildForNode(inputPath, outFile, workingDir) {
  const viewerRoot = path.resolve(__dirname, '..', '..');
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
  const viewerRoot = path.resolve(__dirname, '..', '..');
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
    define: {
      'process.env.NODE_ENV': '"production"'
    }
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
  <title>render-jsx</title>
</head>
<body>
  <div id="root">${ssrMarkup}</div>
</body>
</html>`;
}

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

async function main() {
  const inputArg = process.argv[2];
  if (!inputArg) {
    console.error('Usage: render-jsx <path/to/file.jsx>');
    process.exit(1);
  }

  const inputPath = path.resolve(process.cwd(), inputArg);
  if (!fs.existsSync(inputPath)) {
    console.error(`Input file not found: ${inputPath}`);
    process.exit(1);
  }
  if (!/\.jsx?$/.test(inputPath)) {
    console.error('Input must be a .jsx or .js file that exports default Widget');
    process.exit(1);
  }

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'render-jsx-'));
  const ssrOut = path.join(tmpDir, 'ssr.js');
  const browserOut = path.join(tmpDir, 'client.js');
  const normalizedInput = normalizeJsxToTemp(inputPath, tmpDir);
  const workingDir = path.dirname(inputPath);

  log('Bundling for SSR...');
  await buildForNode(normalizedInput, ssrOut, workingDir);

  const mod = await import(pathToFileURL(ssrOut).href);
  const Widget = mod.default || mod.Widget || mod.Component;
  if (!Widget) {
    console.error('Could not find a default export for the component. Make sure the file exports default function Widget() { ... }');
    process.exit(1);
  }
  log('Rendering SSR markup...');
  const ssrMarkup = ReactDOMServer.renderToString(React.createElement(Widget));

  log('Bundling client for hydration...');
  await buildForBrowser(normalizedInput, browserOut, workingDir);

  const html = htmlTemplate({ ssrMarkup, includeTailwindCdn: true });

  log('Launching headless Chromium...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1200, height: 1000 } });
  const page = await context.newPage();

  await page.setContent(html, { waitUntil: 'load' });
  const clientCode = fs.readFileSync(browserOut, 'utf8');
  await page.addScriptTag({ content: clientCode });

  await page.evaluate(() => { document.body.style.background = 'transparent'; });

  await page.waitForSelector('.widget', { state: 'attached', timeout: 10000 });

  await page.waitForTimeout(100);

  const widget = await page.$('.widget');
  if (!widget) {
    throw new Error('No element with class .widget found in the rendered output.');
  }

  async function measure() {
    return await page.evaluate((el) => {
      const rect = el.getBoundingClientRect();
      return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
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

  log(`Widget size: ${Math.round(box.width)} x ${Math.round(box.height)}`);

  const { dir, name } = path.parse(inputPath);
  const outPath = path.join(dir, `${name}.png`);

  await widget.screenshot({ path: outPath, omitBackground: true });

  await browser.close();
  log(`Saved PNG -> ${outPath}`);
}

main().catch((err) => {
  console.error('[render-jsx] Error:', err);
  process.exit(1);
});

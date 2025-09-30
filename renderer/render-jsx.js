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
  // Simple prefixed log
  console.log('[render-jsx]', ...args);
}

async function buildForNode(inputPath, outFile) {
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
    absWorkingDir: process.cwd(),
    nodePaths: [process.cwd(), path.join(process.cwd(), 'node_modules')],
  });
}

async function buildForBrowser(inputPath, outFile) {
  // Generate a small entry to hydrate the SSR markup
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
    absWorkingDir: process.cwd(),
    nodePaths: [process.cwd(), path.join(process.cwd(), 'node_modules')],
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
    /* Prevent scrollbars by default */
    body { overflow: hidden; }
    /* Make widget shrink-to-fit when author didn't set width */
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
  // Wrap raw <style>...</style> content with template literal if not already wrapped
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

  // Build SSR bundle for Node
  log('Bundling for SSR...');
  await buildForNode(normalizedInput, ssrOut);

  // Import SSR bundle and render to string
  const mod = await import(pathToFileURL(ssrOut).href);
  const Widget = mod.default || mod.Widget || mod.Component;
  if (!Widget) {
    console.error('Could not find a default export for the component. Make sure the file exports default function Widget() { ... }');
    process.exit(1);
  }
  log('Rendering SSR markup...');
  const ssrMarkup = ReactDOMServer.renderToString(React.createElement(Widget));

  // Build client bundle
  log('Bundling client for hydration...');
  await buildForBrowser(normalizedInput, browserOut);

  // Prepare HTML and load in Chromium
  const html = htmlTemplate({ ssrMarkup, includeTailwindCdn: true });

  // Launch Chromium
  log('Launching headless Chromium...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1200, height: 1000 } });
  const page = await context.newPage();

  await page.setContent(html, { waitUntil: 'load' });
  // Inject the client bundle as an inline script to avoid needing an HTTP server
  const clientCode = fs.readFileSync(browserOut, 'utf8');
  await page.addScriptTag({ content: clientCode });

  // Ensure transparent background
  await page.evaluate(() => { document.body.style.background = 'transparent'; });

  // Wait for the .widget element to be in the DOM (from SSR it's there immediately)
  await page.waitForSelector('.widget', { state: 'attached', timeout: 10000 });

  // Wait a tick for hydration and any fonts/icons
  await page.waitForTimeout(100);

  const widget = await page.$('.widget');
  if (!widget) {
    throw new Error('No element with class .widget found in the rendered output.');
  }

  // Measure size. If width/height is 0, wait a bit and re-measure (for Tailwind cdn rendering)
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

  // Adjust viewport if needed
  const vw = Math.max(400, Math.ceil(box.x + box.width + 20));
  const vh = Math.max(400, Math.ceil(box.y + box.height + 20));
  await page.setViewportSize({ width: vw, height: vh });

  // Log size
  log(`Widget size: ${Math.round(box.width)} x ${Math.round(box.height)}`);

  // Output path
  const { dir, name } = path.parse(inputPath);
  const outPath = path.join(dir, `${name}.png`);

  // Screenshot element with transparent background
  await widget.screenshot({ path: outPath, omitBackground: true });

  await browser.close();
  log(`Saved PNG -> ${outPath}`);
}

main().catch((err) => {
  console.error('[render-jsx] Error:', err);
  process.exit(1);
});

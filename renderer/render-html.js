#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright';

function log(...args) {
  console.log('[render-html]', ...args);
}

async function main() {
  const inputArg = process.argv[2];
  if (!inputArg) {
    console.error('Usage: render-html <path/to/file.html>');
    process.exit(1);
  }

  const inputPath = path.resolve(process.cwd(), inputArg);
  if (!fs.existsSync(inputPath)) {
    console.error(`Input file not found: ${inputPath}`);
    process.exit(1);
  }
  if (!/\.html?$/.test(inputPath)) {
    console.error('Input must be a .html file');
    process.exit(1);
  }

  const fileUrl = pathToFileURL(inputPath).href;

  log('Launching headless Chromium...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1200, height: 1000 } });
  const page = await context.newPage();

  // Navigate to the local HTML file so relative URLs work
  await page.goto(fileUrl, { waitUntil: 'load' });

  // Ensure transparent page background outside of the widget
  await page.evaluate(() => {
    document.documentElement.style.background = 'transparent';
    document.body && (document.body.style.background = 'transparent');
    // Avoid scrollbars changing layout
    if (document.body) document.body.style.overflow = 'hidden';
  });

  // Wait for widget to exist
  await page.waitForSelector('.widget', { state: 'attached', timeout: 10000 });

  // Give a brief moment for any hydration (Tailwind CDN, icon libs, etc.)
  await page.waitForTimeout(80);

  const widget = await page.$('.widget');
  if (!widget) {
    throw new Error('No element with class .widget found');
  }

  async function measure() {
    return await page.evaluate((el) => {
      const r = el.getBoundingClientRect();
      return { x: r.x, y: r.y, width: r.width, height: r.height };
    }, widget);
  }

  let box = await measure();
  const t0 = Date.now();
  while ((box.width === 0 || box.height === 0) && Date.now() - t0 < 3000) {
    await page.waitForTimeout(50);
    box = await measure();
  }

  // Adjust viewport so the element is fully visible
  const vw = Math.max(400, Math.ceil(box.x + box.width + 20));
  const vh = Math.max(400, Math.ceil(box.y + box.height + 20));
  await page.setViewportSize({ width: vw, height: vh });

  // Re-measure after viewport adjustment (rarely changes but safe)
  box = await measure();
  log(`Widget size: ${Math.round(box.width)} x ${Math.round(box.height)}`);

  const { dir, name } = path.parse(inputPath);
  const outPath = path.join(dir, `${name}.png`);

  await widget.screenshot({ path: outPath, omitBackground: true });

  await browser.close();
  log(`Saved PNG -> ${outPath}`);
}

main().catch((err) => {
  console.error('[render-html] Error:', err);
  process.exit(1);
});


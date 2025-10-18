import path from 'path';
import fs from 'fs';
import { RESULTS_ROOT } from '../../lib/serverPaths';
import { renderJsxBatch, renderHtmlBatch } from '../../renderer/index.js';

function safe(s) {
  return s && typeof s === 'string' && !s.includes('..') && !s.includes('\\') && s.length < 512;
}

const activeRenders = new Map();

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }

  const { run } = req.body;

  if (!safe(run)) {
    res.status(400).json({ error: 'invalid args' });
    return;
  }

  const runDir = path.join(RESULTS_ROOT, run);

  if (!fs.existsSync(runDir)) {
    res.status(404).json({ error: 'run not found' });
    return;
  }

  const key = run;

  if (activeRenders.has(key)) {
    res.status(200).json({ success: true, message: 'Render already in progress' });
    return;
  }

  try {
    res.status(200).json({ success: true, message: 'Rendering started in background' });

    const renderPromise = (async () => {
      try {
        const imageDirs = fs.readdirSync(runDir, { withFileTypes: true })
          .filter(d => d.isDirectory())
          .map(d => path.join(runDir, d.name));

        console.log(`[batch-render-run] Starting render for ${imageDirs.length} images in run "${run}"`);

        for (const imageDir of imageDirs) {
          try {
            await renderJsxBatch(imageDir).catch((err) => {
              console.log(`[batch-render-run] No JSX files or JSX batch render failed for ${imageDir}:`, err.message);
            });

            await renderHtmlBatch(imageDir).catch((err) => {
              console.log(`[batch-render-run] No HTML files or HTML batch render failed for ${imageDir}:`, err.message);
            });
          } catch (err) {
            console.error(`[batch-render-run] Error rendering ${imageDir}:`, err);
          }
        }

        console.log(`[batch-render-run] Completed for run "${run}"`);
      } finally {
        activeRenders.delete(key);
      }
    })();

    activeRenders.set(key, renderPromise);
  } catch (err) {
    console.error('Batch render run startup error:', err);
    activeRenders.delete(key);
    res.status(500).json({ error: String(err.message || err) });
  }
}

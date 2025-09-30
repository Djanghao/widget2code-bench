import path from 'path';
import fs from 'fs';
import { RESULTS_ROOT } from '../../lib/serverPaths';
import { renderJsxBatch, renderHtmlBatch } from '../../renderer/index.js';

function safe(s) {
  return s && typeof s === 'string' && !s.includes('..') && !s.includes('\\') && s.length < 512;
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }

  const { run, image } = req.body;

  if (!safe(run) || !safe(image)) {
    res.status(400).json({ error: 'invalid args' });
    return;
  }

  const base = path.join(RESULTS_ROOT, run, image);

  if (!fs.existsSync(base)) {
    res.status(404).json({ error: 'not found' });
    return;
  }

  try {
    const jsxPromise = renderJsxBatch(base).catch((err) => {
      console.log('No JSX files or JSX batch render failed:', err.message);
    });

    const htmlPromise = renderHtmlBatch(base).catch((err) => {
      console.log('No HTML files or HTML batch render failed:', err.message);
    });

    await Promise.all([jsxPromise, htmlPromise]);

    res.status(200).json({ success: true });
  } catch (err) {
    console.error('Batch render error:', err);
    res.status(500).json({ error: String(err.message || err) });
  }
}

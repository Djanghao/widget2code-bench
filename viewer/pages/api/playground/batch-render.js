import { renderJsxBatch, renderHtmlBatch } from '../../../renderer/index.js';
import { TMP_PLAYGROUND_ROOT } from '../../../lib/serverPaths';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }
  try {
    const jsxPromise = renderJsxBatch(TMP_PLAYGROUND_ROOT).catch((err) => {
      console.log('[playground] JSX batch render skipped/failed:', err?.message || err);
    });
    const htmlPromise = renderHtmlBatch(TMP_PLAYGROUND_ROOT).catch((err) => {
      console.log('[playground] HTML batch render skipped/failed:', err?.message || err);
    });
    await Promise.all([jsxPromise, htmlPromise]);
    res.status(200).json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: String(err?.message || err) });
  }
}

